from pathlib import Path

import pytest

from storyforge.config import Settings
from storyforge.db import factory, make_engine
from storyforge.service import StoryService


@pytest.fixture()
def service(tmp_path: Path):
    engine = make_engine("sqlite+pysqlite:///" + str(tmp_path / "test.db"))
    yield StoryService(factory(engine))
    engine.dispose()


@pytest.fixture()
def settings(tmp_path: Path):
    return Settings(
        mode="demo",
        database=str(tmp_path / "web.db"),
        secret="s" * 48,
        demo_password="s3cure-demo-pass",
    )
