"""Python-authored StoryForge web application and host controls."""

from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

import httpx
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import MutableHeaders
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .ai import DemoGenerator, OpenAICompatibleGenerator
from .avatars import ACCESSORIES, ARCHETYPES, PALETTES, TRAITS, render_avatar
from .config import Settings
from .db import factory, make_engine
from .graph import render_tree
from .service import StoryError, StoryService
from .twitch import TwitchConnector, exchange_code, login_url, save_host_token, user_for_token

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger(__name__)


def _origin(value: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme.casefold(), parsed.hostname.casefold().rstrip("."), port
    except ValueError:
        return None


def _request_matches_configured_origin(request: Request, base_url: str) -> bool:
    return _origin(str(request.url)) == _origin(base_url)


class ConfiguredOriginMiddleware:
    """Redirect to the trusted browser origin and add security headers."""

    def __init__(self, app: ASGIApp, *, base_url: str):
        self.app = app
        self.base_url = base_url

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Cache-Control"] = "no-store"
                frame_policy = (
                    "frame-ancestors *"
                    if request.url.path == "/overlay"
                    else "frame-ancestors 'none'"
                )
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'none'; "
                    "style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; "
                    "base-uri 'none'; form-action 'self'; " + frame_policy
                )
            await send(message)

        if _request_matches_configured_origin(request, self.base_url):
            await self.app(scope, receive, send_with_headers)
            return

        current = request.url
        target = self.base_url + current.path
        if current.query:
            target += "?" + current.query
        response = RedirectResponse(target, status_code=307)
        await response(scope, receive, send_with_headers)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_environment()
    settings.validate()
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)
    generator = OpenAICompatibleGenerator(settings) if settings.ai_enabled else DemoGenerator()
    connector = TwitchConnector(settings, sessions, service)
    generation_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(connector.run_forever())
        yield
        connector.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        engine.dispose()

    app = FastAPI(title="AI StoryForge", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret,
        same_site="lax",
        https_only=settings.base_url.startswith("https://"),
        max_age=60 * 60 * 8,
    )
    app.add_middleware(ConfiguredOriginMiddleware, base_url=settings.base_url)
    app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "templates")
    app.state.service = service
    app.state.connector = connector
    app.state.settings = settings

    def csrf(request: Request) -> str:
        if "csrf" not in request.session:
            request.session["csrf"] = secrets.token_urlsafe(28)
        return request.session["csrf"]

    def require_csrf(request: Request, value: str) -> None:
        if not secrets.compare_digest(value, str(request.session.get("csrf", ""))) or not value:
            raise HTTPException(status_code=403, detail="Invalid CSRF token")

    def is_host(request: Request) -> bool:
        return request.session.get("role") == "host"

    def host_only(request: Request) -> None:
        if not is_host(request):
            raise HTTPException(status_code=403, detail="Host authentication required")

    def viewer_identity(request: Request) -> str:
        user_id = request.session.get("twitch_user_id")
        if not user_id:
            raise HTTPException(status_code=403, detail="Twitch login required")
        return str(user_id)

    def is_loopback_request(request: Request) -> bool:
        client = request.client
        if client is None or request.url.hostname is None:
            return False
        try:
            remote = ip_address(client.host)
        except ValueError:
            return False
        return remote.is_loopback and request.url.hostname.casefold().rstrip(".") in {
            "localhost",
            "127.0.0.1",
            "::1",
        }

    def view(request: Request, page: str, **context) -> HTMLResponse:
        data = dict(
            request=request,
            csrf=csrf(request),
            host=is_host(request),
            demo=settings.mode == "demo",
            status=connector.status,
            error=connector.last_error,
            message=request.query_params.get("msg", ""),
            archetypes=ARCHETYPES,
            traits=TRAITS,
            palettes=tuple(PALETTES),
            accessories=ACCESSORIES,
            **context,
        )
        return templates.TemplateResponse(request, page, data)

    def go(path: str, message: str = "") -> RedirectResponse:
        return RedirectResponse(
            path + ("?msg=" + quote(message[:200]) if message else ""), status_code=303
        )

    async def generate_scene_locked() -> None:
        data = service.generator_context()
        service.mark_generation_started()
        try:
            result = await generator.generate(**data)
        except Exception:
            service.mark_generation_failed()
            raise
        service.save_proposal(result, "AI" if settings.ai_enabled else "DEMO")

    async def generate_scene() -> None:
        if generation_lock.locked():
            raise StoryError("A scene generation is already in progress")
        async with generation_lock:
            await generate_scene_locked()

    @app.get("/health")
    def health():
        snapshot = service.snapshot()
        latest_generation = snapshot.get("proposal") or snapshot.get("node")
        provenance = latest_generation.get("provenance") if latest_generation else None
        if provenance == "AI":
            ai_generation = "VERIFIED"
        elif provenance == "DEMO":
            ai_generation = "DEMO"
        else:
            ai_generation = "NOT GENERATED"
        return {
            "app": "AI StoryForge",
            "status": "ok",
            "mode": settings.mode,
            "twitch": connector.status,
            "eventsub_subscribed": connector.status == "LIVE_TWITCH",
            "last_real_chat_event_seen": connector.last_event is not None,
            **connector.chat_health(),
            "ai_provider": "CONFIGURED" if settings.ai_enabled else "DEMO",
            "ai_last_generation": ai_generation,
        }

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return view(request, "index.html", snap=service.snapshot())

    @app.get("/host", response_class=HTMLResponse)
    def host(request: Request):
        host_only(request)
        snapshot = service.snapshot()
        return view(request, "host.html", snap=snapshot)

    @app.get("/overlay", response_class=HTMLResponse)
    def overlay(request: Request):
        snap = service.snapshot()
        return view(request, "overlay.html", snap=snap)

    @app.get("/graph.svg")
    def graph_svg():
        snap = service.snapshot()
        return Response(render_tree(snap.get("nodes", [])), media_type="image/svg+xml")

    @app.get("/avatar/{persona_id}.svg")
    def avatar(persona_id: int):
        with sessions() as db:
            from .models import Persona

            p = db.get(Persona, persona_id)
            if not p or not p.visible:
                raise HTTPException(404, "Persona not found")
            svg = render_avatar(p)
        return Response(
            svg,
            media_type="image/svg+xml",
            headers={"Content-Security-Policy": "default-src 'none'; style-src 'none'; sandbox"},
        )

    @app.get("/profile", response_class=HTMLResponse)
    def profile(request: Request):
        user_id = viewer_identity(request)
        p = service.persona(user_id)
        return view(request, "profile.html", persona=p)

    @app.post("/profile/edit")
    def profile_edit(
        request: Request,
        csrf_token: str = Form(""),
        alias: str = Form(""),
        archetype: str = Form("explorer"),
        trait: str = Form("curious"),
        palette: str = Form("violet"),
        accessory: str = Form("star"),
    ):
        require_csrf(request, csrf_token)
        user_id = viewer_identity(request)
        try:
            service.update_persona(
                user_id,
                alias=alias,
                archetype=archetype,
                trait=trait,
                palette=palette,
                accessory=accessory,
            )
            return go("/profile", "Persona saved")
        except StoryError as exc:
            return go("/profile", str(exc))

    @app.post("/profile/delete")
    def profile_delete(request: Request, csrf_token: str = Form("")):
        require_csrf(request, csrf_token)
        service.delete_persona(viewer_identity(request))
        return go("/profile", "Persona and identifiable contributions deleted")

    @app.post("/auth/demo")
    def demo_login(request: Request, csrf_token: str = Form(""), password: str = Form("")):
        require_csrf(request, csrf_token)
        if settings.mode != "demo" or not settings.demo_password:
            raise HTTPException(403, "Demo login unavailable")
        if not is_loopback_request(request):
            raise HTTPException(403, "Demo host login is available only from loopback")
        if not secrets.compare_digest(password, settings.demo_password):
            return go("/", "Incorrect demo password")
        request.session["role"] = "host"
        request.session["twitch_user_id"] = "demo-host"
        request.session["display_name"] = "StoryMaster"
        service.get_or_create_persona("demo-host", "StoryMaster", is_host=True)
        return go("/host", "Demo host authenticated")

    @app.get("/auth/twitch")
    def twitch_login(request: Request, role: str = "viewer"):
        if role not in {"viewer", "host"}:
            raise HTTPException(400, "Invalid role")
        if not settings.twitch_client_id or not settings.twitch_client_secret:
            raise HTTPException(503, "Twitch OAuth not configured")
        if not _request_matches_configured_origin(request, settings.base_url):
            canonical_login = f"{settings.base_url}/auth/twitch?{urlencode({'role': role})}"
            return RedirectResponse(canonical_login, status_code=307)
        state = secrets.token_urlsafe(28)
        request.session["oauth_state"] = state
        request.session["oauth_role"] = role
        return RedirectResponse(login_url(settings, role=role, state=state))

    @app.get("/auth/callback")
    async def twitch_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        callback_failure = "Twitch sign-in could not be completed. Please start again."

        if not _request_matches_configured_origin(request, settings.base_url):
            if code and state:
                canonical_callback = (
                    f"{settings.base_url}/auth/callback?{urlencode({'code': code, 'state': state})}"
                )
                return RedirectResponse(canonical_callback, status_code=307)
            return go(settings.base_url, callback_failure)

        expected = str(request.session.get("oauth_state", ""))
        if not state:
            return go(settings.base_url, callback_failure)
        if not expected:
            return go(settings.base_url, callback_failure)
        if not secrets.compare_digest(state, expected):
            return go(settings.base_url, callback_failure)
        if error:
            if error == "redirect_mismatch":
                return go(
                    settings.base_url,
                    "Twitch rejected the callback URL. Register APP_BASE_URL/auth/callback exactly.",
                )
            return go(settings.base_url, "Twitch authorization was not approved. Start again.")
        if not code:
            return go(settings.base_url, callback_failure)
        role = request.session.pop("oauth_role", "viewer")
        request.session.pop("oauth_state", None)
        try:
            token = await exchange_code(settings, code)
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            LOGGER.warning("Twitch OAuth token exchange failed (HTTP %s)", status)
            return go(
                settings.base_url,
                f"Twitch token exchange failed (HTTP {status}). Verify the registered callback URL and Twitch app credentials.",
            )
        except httpx.HTTPError as exc:
            LOGGER.warning("Twitch OAuth token exchange failed (%s)", type(exc).__name__)
            return go(
                settings.base_url,
                "Twitch token exchange could not reach Twitch. Check network access and retry.",
            )
        except (ValueError, KeyError) as exc:
            LOGGER.warning("Twitch OAuth token response was invalid (%s)", type(exc).__name__)
            return go(settings.base_url, callback_failure)
        try:
            user = await user_for_token(settings, token["access_token"])
        except httpx.HTTPStatusError as exc:
            LOGGER.warning("Twitch identity lookup failed (HTTP %s)", exc.response.status_code)
            return go(settings.base_url, callback_failure)
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            LOGGER.warning("Twitch identity lookup failed (%s)", type(exc).__name__)
            return go(settings.base_url, callback_failure)
        uid = str(user["id"])
        if role == "host":
            if uid != settings.twitch_broadcaster_id or uid != settings.twitch_reader_id:
                return go(settings.base_url, callback_failure)
            save_host_token(settings, sessions, token)
        request.session["role"] = "host" if role == "host" else "viewer"
        request.session["twitch_user_id"] = uid
        request.session["display_name"] = str(user.get("display_name", "Viewer"))[:80]
        service.get_or_create_persona(uid, request.session["display_name"], is_host=role == "host")
        return go("/host" if role == "host" else "/profile", "Twitch account connected")

    @app.post("/auth/logout")
    def logout(request: Request, csrf_token: str = Form("")):
        require_csrf(request, csrf_token)
        request.session.clear()
        return go("/", "Signed out")

    @app.post("/host/story")
    async def host_story(
        request: Request,
        csrf_token: str = Form(""),
        title: str = Form(""),
        premise: str = Form(""),
        tone: str = Form("mystery"),
    ):
        host_only(request)
        require_csrf(request, csrf_token)
        try:
            if generation_lock.locked():
                raise StoryError("A scene generation is already in progress")
            async with generation_lock:
                service.create_story(title, premise, tone)
                await generate_scene_locked()
            return go("/host", "Scene proposal generated; review before publishing")
        except StoryError as exc:
            return go("/host", "Story setup/generation: " + str(exc)[:160])
        except (ValueError, httpx.HTTPError) as exc:
            return go(
                "/host", "Generation failed (" + type(exc).__name__ + "); retry from Host Studio"
            )

    @app.post("/host/action")
    async def host_action(
        request: Request,
        csrf_token: str = Form(""),
        action: str = Form(""),
        item_id: int = Form(0),
        text: str = Form(""),
    ):
        host_only(request)
        require_csrf(request, csrf_token)
        try:
            if action == "approve":
                service.approve_proposal()
            elif action == "start_vote":
                service.start_voting()
            elif action == "close_vote":
                selection = service.close_voting()
                try:
                    await generate_scene()
                except Exception as exc:  # noqa: BLE001 - keep host informed of provider failures
                    return go(
                        "/host",
                        "Vote resolved ("
                        + selection
                        + "); generation failed ("
                        + type(exc).__name__
                        + "); retry from Host Studio",
                    )
            elif action == "retry_generation":
                await generate_scene()
            elif action in {"pause", "resume", "finish"}:
                service.set_stage(
                    {"pause": "PAUSED", "resume": "READY", "finish": "FINISHED"}[action]
                )
            elif action == "fork":
                service.fork_from(item_id)
            elif action in {"approve_contribution", "reject_contribution"}:
                service.moderate(item_id, action == "approve_contribution")
            elif action in {"line", "twist", "act"}:
                service.add_contribution(
                    str(request.session.get("twitch_user_id", "demo-host")),
                    action,
                    text,
                    approved=True,
                )
            else:
                raise StoryError("Unknown host action")
            return go("/host", "Action completed: " + action)
        except StoryError as exc:
            return go("/host", "Action failed: " + str(exc)[:120])
        except Exception as exc:  # noqa: BLE001 - convert provider failures to safe UI feedback
            return go("/host", "Action failed (" + type(exc).__name__ + ")")

    @app.post("/host/simulate")
    def host_simulate(
        request: Request,
        csrf_token: str = Form(""),
        viewer: str = Form(""),
        command: str = Form(""),
    ):
        host_only(request)
        require_csrf(request, csrf_token)
        if settings.mode != "demo":
            raise HTTPException(403, "Simulation available only in demo mode")
        viewer = viewer.strip()
        if not 2 <= len(viewer) <= 30 or not all(c.isalnum() or c in "_-" for c in viewer):
            return go("/host", "Invalid demo viewer name")
        import hashlib

        viewer_id = "demo-" + hashlib.sha256(viewer.lower().encode()).hexdigest()[:16]
        outcome = service.process_chat(secrets.token_hex(16), viewer_id, viewer, command)
        return go("/host", "SIMULATED event: " + outcome)

    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_environment()
    settings.validate()
    print(f"Open StoryForge at {settings.base_url}", flush=True)
    if settings.base_url.startswith("http://"):
        print(
            "This runner serves plain HTTP; use the URL exactly as printed (do not switch to https).",
            flush=True,
        )
    else:
        print(
            "APP_BASE_URL uses HTTPS; a TLS reverse proxy must forward requests to this local Uvicorn server.",
            flush=True,
        )
    uvicorn.run(
        "storyforge.app:create_app",
        host="127.0.0.1",
        port=8000,
        factory=True,
        access_log=False,
    )


if __name__ == "__main__":
    main()
