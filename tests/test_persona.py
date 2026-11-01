import pytest
from sqlalchemy import select

from storyforge.avatars import render_avatar
from storyforge.models import PersonaRevision
from storyforge.service import StoryError


def test_persona_persists_and_is_deterministic(service):
    p = service.get_or_create_persona("100", "Starlight")
    assert p.archetype == "explorer"
    img = render_avatar(p)
    assert img == render_avatar(service.persona("100"))
    assert "<script" not in img
    edited = service.update_persona(
        "100",
        alias="Nova Star",
        archetype="scholar",
        trait="curious",
        palette="azure",
        accessory="moon",
    )
    assert edited.revision == 2
    assert img != render_avatar(edited)
    assert render_avatar(edited) == render_avatar(service.persona("100"))
    assert "<svg" in render_avatar(edited, size=512)
    with service.sessions() as db:
        revisions = list(
            db.scalars(select(PersonaRevision).where(PersonaRevision.persona_id == edited.id))
        )
        assert len(revisions) == 2


def test_invalid_profile_edit_rejected(service):
    service.get_or_create_persona("12", "Visitor")
    with pytest.raises(StoryError):
        service.update_persona("12", alias="<script>alert(1)</script>")
    with pytest.raises(StoryError):
        service.update_persona("12", archetype="moderator")
    with pytest.raises(ValueError):
        render_avatar(service.persona("12"), size=900)


def test_persona_opt_out_pseudonymizes_previous_votes(service):
    service.get_or_create_persona("33", "Ada")
    assert service.delete_persona("33") is True
    assert service.persona("33") is None
    assert service.delete_persona("33") is False
