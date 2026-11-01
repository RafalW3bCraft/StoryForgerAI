import pytest
from fastapi.testclient import TestClient

from storyforge.app import create_app


def _login(client, password="s3cure-demo-pass"):
    client.get("/")
    from bs4 import BeautifulSoup

    r = client.get("/")
    soup = BeautifulSoup(r.text, "html.parser")
    csrf = soup.select_one('form[action="/auth/demo"] input[name="csrf_token"]')["value"]
    response = client.post(
        "/auth/demo", data={"csrf_token": csrf, "password": password}, follow_redirects=False
    )
    return response, csrf


def test_host_authorization_and_csrf(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert c.get("/host").status_code == 403
        response, _csrf = _login(c, password="wrong")
        assert response.status_code == 303
        assert c.get("/host").status_code == 403
        response, _csrf = _login(c)
        assert response.status_code == 303
        assert c.get("/host").status_code == 200
        assert (
            c.post(
                "/host/story",
                data={
                    "csrf_token": "wrong",
                    "title": "Test World",
                    "premise": "An extremely memorable test world appears.",
                },
            ).status_code
            == 403
        )


def test_end_to_end_web_demo(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        response, csrf = _login(c)
        assert response.status_code == 303
        r = c.post(
            "/host/story",
            data={
                "csrf_token": csrf,
                "title": "The Glass Archive",
                "premise": "A place where memories are stored in glass forever.",
                "tone": "mystery",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "PENDING HOST APPROVAL" in r.text
        c.post("/host/action", data={"csrf_token": csrf, "action": "approve"})
        r = c.post(
            "/host/action", data={"csrf_token": csrf, "action": "start_vote"}, follow_redirects=True
        )
        assert "VOTING" in r.text
        for viewer, command in [
            ("Luna", "!join"),
            ("Luna", "!persona scholar"),
            ("Luna", "!vote B"),
            ("Sol", "!join"),
            ("Sol", "!vote B"),
            ("Sol", "!line I found a map"),
        ]:
            r = c.post(
                "/host/simulate",
                data={"csrf_token": csrf, "viewer": viewer, "command": command},
                follow_redirects=True,
            )
            assert r.status_code == 200
        snap = app.state.service.snapshot()
        assert snap["round"]["votes"]["B"] == 2
        assert len(snap["personas"]) >= 3
        assert any(x.status == "PENDING" for x in snap["contributions"])
        c.post("/host/action", data={"csrf_token": csrf, "action": "close_vote"})
        r = c.post(
            "/host/action", data={"csrf_token": csrf, "action": "approve"}, follow_redirects=True
        )
        assert r.status_code == 200
        assert len(app.state.service.snapshot()["nodes"]) == 2
        assert c.get("/overlay").status_code == 200
        assert "SYNTHETIC DEMO" in c.get("/overlay").text
        assert c.get("/graph.svg").status_code == 200
        p = app.state.service.list_personas()[0]
        assert "<svg" in c.get(f"/avatar/{p.id}.svg").text


def test_live_config_requires_credentials(tmp_path):

    from storyforge.config import Settings

    with pytest.raises(ValueError):
        create_app(Settings(mode="live", database=str(tmp_path / "bad.db"), secret="x" * 40))


def test_public_routes_do_not_expose_host_mutations(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get("/profile").status_code == 403
        assert c.get("/host").status_code == 403
        assert (
            c.post("/host/action", data={"action": "finish", "csrf_token": "bad"}).status_code
            == 403
        )
        assert (
            c.post("/profile/edit", data={"alias": "Intruder", "csrf_token": "bad"}).status_code
            == 403
        )
        assert (
            c.post(
                "/host/simulate", data={"viewer": "X", "command": "!join", "csrf_token": "bad"}
            ).status_code
            == 403
        )
        assert c.get("/auth/callback?code=bogus&state=bogus").status_code == 403


def test_live_oauth_configuration_rejects_missing_secrets(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    s = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        twitch_client_id="id",
        twitch_client_secret="secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
    )
    create_app(s)
    from storyforge.twitch import login_url

    url = login_url(s, role="host", state="state-abc")
    assert "user%3Aread%3Achat" in url
    assert "state-abc" in url
    with pytest.raises(ValueError):
        login_url(s, role="admin", state="bad")


def test_live_configuration_requires_single_account_reader(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        twitch_client_id="id",
        twitch_client_secret="secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="222",
        token_key=Fernet.generate_key().decode(),
    )
    with pytest.raises(ValueError, match="TWITCH_READER_ID"):
        settings.validate()


def test_demo_mode_never_implicitly_enables_external_ai():
    from storyforge.config import Settings

    settings = Settings(
        mode="demo",
        ai_base_url="https://provider.test/v1",
        ai_api_key="configured-but-not-live",
        ai_model="test-model",
    )
    assert settings.ai_enabled is False
