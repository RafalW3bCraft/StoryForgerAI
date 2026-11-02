"""Relational domain model. Canonical state is persisted transactionally."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Persona(Base):
    __tablename__ = "personas"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    twitch_user_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    alias: Mapped[str] = mapped_column(String(40))
    archetype: Mapped[str] = mapped_column(String(32), default="explorer")
    trait: Mapped[str] = mapped_column(String(32), default="curious")
    palette: Mapped[str] = mapped_column(String(32), default="violet")
    accessory: Mapped[str] = mapped_column(String(32), default="star")
    seed: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PersonaRevision(Base):
    __tablename__ = "persona_revisions"
    __table_args__ = (UniqueConstraint("persona_id", "revision"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    persona_id: Mapped[int] = mapped_column(ForeignKey("personas.id"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class World(Base):
    __tablename__ = "worlds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    premise: Mapped[str] = mapped_column(Text)
    tone: Mapped[str] = mapped_column(String(32), default="mystery")


class StorySession(Base):
    __tablename__ = "story_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    world_id: Mapped[int] = mapped_column(ForeignKey("worlds.id"))
    stage: Mapped[str] = mapped_column(String(24), default="REVIEW")
    current_node_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_round_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_proposal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paused_from_stage: Mapped[str | None] = mapped_column(String(24), nullable=True)
    generation_status: Mapped[str] = mapped_column(String(24), default="AWAITING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StoryNode(Base):
    __tablename__ = "story_nodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("story_sessions.id"), index=True)
    parent_node_id: Mapped[int | None] = mapped_column(ForeignKey("story_nodes.id"))
    title: Mapped[str] = mapped_column(String(120))
    narrative: Mapped[str] = mapped_column(Text)
    choices_json: Mapped[str] = mapped_column(Text)
    selected_choice: Mapped[str | None] = mapped_column(String(8), nullable=True)
    provenance: Mapped[str] = mapped_column(String(20), default="DEMO")
    is_canon: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VotingRound(Base):
    __tablename__ = "voting_rounds"
    __table_args__ = (
        Index(
            "uq_open_voting_round_per_session",
            "session_id",
            unique=True,
            sqlite_where=text("status = 'OPEN'"),
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("story_sessions.id"), index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("story_nodes.id"))
    options_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="OPEN")
    winning_choice: Mapped[str | None] = mapped_column(String(8))


class ViewerVote(Base):
    __tablename__ = "viewer_votes"
    __table_args__ = (UniqueConstraint("round_id", "viewer_id"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("voting_rounds.id"), index=True)
    viewer_id: Mapped[str] = mapped_column(String(128))
    selection: Mapped[str] = mapped_column(String(8))


class SceneProposal(Base):
    __tablename__ = "scene_proposals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("story_sessions.id"))
    parent_node_id: Mapped[int | None] = mapped_column(ForeignKey("story_nodes.id"))
    selected_choice: Mapped[str | None] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(120))
    narrative: Mapped[str] = mapped_column(Text)
    choices_json: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15), default="PENDING")


class Contribution(Base):
    __tablename__ = "contributions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("story_sessions.id"))
    twitch_user_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")


class EventReceipt(Base):
    __tablename__ = "event_receipts"
    message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TokenVault(Base):
    __tablename__ = "token_vault"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    encrypted_json: Mapped[str] = mapped_column(Text)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(64))
    details: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RuntimeSetting(Base):
    """Small durable operator preferences; secrets never belong in this table."""

    __tablename__ = "runtime_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))
