"""Runtime configuration; secrets stay out of serialized browser sessions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mode: str = field(default_factory=lambda: os.environ.get("STORYFORGE_MODE", "demo").lower())
    database: str = field(
        default_factory=lambda: os.environ.get("STORYFORGE_DATABASE", "./storyforge.db")
    )
    secret: str = field(
        default_factory=lambda: os.environ.get("STORYFORGE_SECRET", "development-only-change-me"),
        repr=False,
    )
    demo_password: str = field(
        default_factory=lambda: os.environ.get("DEMO_ADMIN_PASSWORD", ""), repr=False
    )
    base_url: str = field(
        default_factory=lambda: os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    )
    twitch_client_id: str = field(default_factory=lambda: os.environ.get("TWITCH_CLIENT_ID", ""))
    twitch_client_secret: str = field(
        default_factory=lambda: os.environ.get("TWITCH_CLIENT_SECRET", ""), repr=False
    )
    twitch_broadcaster_id: str = field(
        default_factory=lambda: os.environ.get("TWITCH_BROADCASTER_ID", "")
    )
    twitch_reader_id: str = field(default_factory=lambda: os.environ.get("TWITCH_READER_ID", ""))
    token_key: str = field(
        default_factory=lambda: os.environ.get("TOKEN_ENCRYPTION_KEY", ""), repr=False
    )
    ai_base_url: str = field(default_factory=lambda: os.environ.get("AI_BASE_URL", ""))
    ai_api_key: str = field(default_factory=lambda: os.environ.get("AI_API_KEY", ""), repr=False)
    ai_model: str = field(default_factory=lambda: os.environ.get("AI_MODEL", ""))

    @classmethod
    def from_environment(cls) -> Settings:
        """Load the CLI's .env file explicitly; importing settings has no side effects."""
        load_dotenv()
        return cls()

    def validate(self) -> None:
        if self.mode not in {"demo", "live"}:
            raise ValueError("STORYFORGE_MODE must be demo or live")
        try:
            base = urlsplit(self.base_url)
            local_http = base.scheme == "http" and base.hostname in {
                "localhost",
                "127.0.0.1",
                "::1",
            }
            valid_base = (
                (base.scheme == "https" or local_http)
                and bool(base.hostname)
                and not base.username
                and not base.password
                and not base.query
                and not base.fragment
                and base.path in {"", "/"}
            )
        except ValueError:
            valid_base = False
        if not valid_base:
            raise ValueError("APP_BASE_URL must be an HTTPS origin or an HTTP loopback origin")
        if self.mode == "live":
            # This insecure demo sentinel is explicitly rejected in live mode.
            if len(self.secret) < 32 or self.secret == "development-only-change-me":  # nosec B105
                raise ValueError("Set a unique STORYFORGE_SECRET of at least 32 characters")
            if not all(
                (
                    self.twitch_client_id,
                    self.twitch_client_secret,
                    self.twitch_broadcaster_id,
                    self.twitch_reader_id,
                    self.token_key,
                )
            ):
                raise ValueError("Live mode requires Twitch and token encryption configuration")
            if self.twitch_reader_id != self.twitch_broadcaster_id:
                raise ValueError(
                    "Live mode requires TWITCH_READER_ID to equal TWITCH_BROADCASTER_ID"
                )
            if not (
                self.twitch_broadcaster_id.isascii()
                and self.twitch_broadcaster_id.isdecimal()
                and self.twitch_reader_id.isascii()
                and self.twitch_reader_id.isdecimal()
            ):
                raise ValueError(
                    "TWITCH_BROADCASTER_ID and TWITCH_READER_ID must be numeric Twitch IDs"
                )
            from cryptography.fernet import Fernet

            Fernet(self.token_key.encode())
            if not all((self.ai_base_url, self.ai_api_key, self.ai_model)):
                raise ValueError("Live mode requires AI_BASE_URL, AI_API_KEY and AI_MODEL")
        if not self.database:
            raise ValueError("Database path is required")

    @property
    def db_url(self) -> str:
        if self.database == ":memory:":
            return "sqlite+pysqlite:///:memory:"
        return "sqlite+pysqlite:///" + str(Path(self.database).resolve())

    @property
    def ai_enabled(self) -> bool:
        # Demo mode must remain deterministic even if a developer's shell has
        # provider variables loaded.  Live mode is the explicit opt-in for
        # external inference; failures are surfaced by the host action.
        return self.mode == "live" and bool(self.ai_base_url and self.ai_api_key and self.ai_model)
