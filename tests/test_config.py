import os
import subprocess
import sys
from pathlib import Path


def test_importing_settings_does_not_load_dotenv(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    script = (
        "import dotenv\n"
        "def reject(*args, **kwargs):\n"
        "    raise AssertionError('dotenv loaded during import')\n"
        "dotenv.load_dotenv = reject\n"
        "from storyforge.config import Settings\n"
        "print(Settings().mode)\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(source)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )

    assert result.returncode == 0, "settings import must not read a local .env file"
    assert result.stdout.strip() == "demo"
    assert "STORYFORGE_SECRET" not in result.stdout


def test_runtime_settings_load_dotenv_explicitly(monkeypatch):
    from storyforge import config

    calls = []
    monkeypatch.setattr(config, "load_dotenv", lambda: calls.append("loaded"))

    config.Settings.from_environment()

    assert calls == ["loaded"]
