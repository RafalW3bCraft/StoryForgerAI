"""Runtime configuration; secrets stay out of serialized browser sessions."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    mode: str = os.environ.get("STORYFORGE_MODE", "demo").lower()
    database: str = os.environ.get("STORYFORGE_DATABASE", "./storyforge.db")
    secret: str = os.environ.get("STORYFORGE_SECRET", "development-only-change-me")
    demo_password: str = os.environ.get("DEMO_ADMIN_PASSWORD", "")
    base_url: str = os.environ.get("APP_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    twitch_client_id: str = os.environ.get("TWITCH_CLIENT_ID", "")
    twitch_client_secret: str = os.environ.get("TWITCH_CLIENT_SECRET", "")
    twitch_broadcaster_id: str = os.environ.get("TWITCH_BROADCASTER_ID", "")
    twitch_reader_id: str = os.environ.get("TWITCH_READER_ID", "")
    token_key: str = os.environ.get("TOKEN_ENCRYPTION_KEY", "")
    ai_base_url: str = os.environ.get("AI_BASE_URL", "")
    ai_api_key: str = os.environ.get("AI_API_KEY", "")
    ai_model: str = os.environ.get("AI_MODEL", "")

    def validate(self) -> None:
        if self.mode not in {"demo", "live"}:
            raise ValueError("STORYFORGE_MODE must be demo or live")
        if self.mode == "live":
            if len(self.secret) < 32 or self.secret == "development-only-change-me":
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
            from cryptography.fernet import Fernet

            Fernet(self.token_key.encode())
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
