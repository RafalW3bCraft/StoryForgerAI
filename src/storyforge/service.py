"""Atomic story transitions and Twitch command application."""

from __future__ import annotations

import json
import re
import time
from collections import Counter, OrderedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .ai import NarrativeProposal
from .avatars import ACCESSORIES, ARCHETYPES, PALETTES, TRAITS, choose_random_seed
from .models import (
    AuditEvent,
    Contribution,
    EventReceipt,
    Persona,
    PersonaRevision,
    SceneProposal,
    StoryNode,
    StorySession,
    ViewerVote,
    VotingRound,
    World,
)


class StoryError(ValueError):
    pass


CHAT_COMMAND_COOLDOWN_SECONDS = 0.75
MAX_COOLDOWN_IDENTITIES = 2048
MAX_RECENT_REJECTED_EVENTS = 4096
REJECTED_EVENT_TTL_SECONDS = 600
CHAT_COMMANDS = frozenset(
    {
        "!join",
        "!leave",
        "!help",
        "!persona",
        "!trait",
        "!avatar",
        "!vote",
        "!line",
        "!twist",
        "!act",
        "!story",
        "!profile",
        "!recap",
    }
)


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def _revision(db: Session, persona: Persona) -> None:
    snapshot = {
        k: getattr(persona, k)
        for k in ("alias", "archetype", "trait", "palette", "accessory", "seed", "visible")
    }
    db.add(
        PersonaRevision(
            persona_id=persona.id, revision=persona.revision, state_json=_json(snapshot)
        )
    )


class StoryService:
    def __init__(self, sessions: sessionmaker):
        self.sessions = sessions
        self._clock = time.monotonic
        # This MVP is deliberately single-process. The bounded cooldown maps
        # reduce per-viewer spam; accepted command receipts remain durable.
        self._last_contribution_command: dict[str, float] = {}
        self._last_chat_command: dict[str, float] = {}
        self._recent_rejected_events: OrderedDict[str, float] = OrderedDict()

    def _active(self, db: Session) -> StorySession | None:
        return db.scalar(select(StorySession).order_by(StorySession.id.desc()).limit(1))

    def get_or_create_persona(
        self, user_id: str, display: str, *, is_host: bool = False
    ) -> Persona:
        if not user_id or len(user_id) > 128:
            raise StoryError("Invalid Twitch user ID")
        with self.sessions.begin() as db:
            persona = db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))
            if persona is None:
                persona = Persona(
                    twitch_user_id=user_id,
                    display_name=display[:80],
                    alias=re.sub(r"[^\w -]", "", display)[:40] or "Wanderer",
                    seed=choose_random_seed(),
                    is_host=is_host,
                )
                db.add(persona)
                db.flush()
                _revision(db, persona)
            else:
                persona.display_name = display[:80]
                if is_host:
                    persona.is_host = True
            return persona

    def update_persona(
        self,
        user_id: str,
        *,
        alias: str | None = None,
        archetype: str | None = None,
        trait: str | None = None,
        palette: str | None = None,
        accessory: str | None = None,
    ) -> Persona:
        with self.sessions.begin() as db:
            persona = db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))
            if not persona:
                raise StoryError("Join before editing a persona")
            if alias is not None:
                alias = alias.strip()
                if not 2 <= len(alias) <= 40 or not re.fullmatch(r"[\w -]+", alias):
                    raise StoryError("Alias must be 2–40 letters, numbers, spaces, _ or -")
                persona.alias = alias
            for field, value, valid in (
                ("archetype", archetype, ARCHETYPES),
                ("trait", trait, TRAITS),
                ("palette", palette, tuple(PALETTES)),
                ("accessory", accessory, ACCESSORIES),
            ):
                if value is not None:
                    if value not in valid:
                        raise StoryError("Invalid " + field)
                    setattr(persona, field, value)
            persona.revision += 1
            db.flush()
            _revision(db, persona)
            return persona

    def _delete_persona_in_db(self, db: Session, user_id: str) -> bool:
        """Delete a profile and pseudonymize its historical participation."""
        persona = db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))
        if not persona:
            return False
        revisions = list(
            db.scalars(select(PersonaRevision).where(PersonaRevision.persona_id == persona.id))
        )
        for rev in revisions:
            db.delete(rev)
        import hashlib

        anon = "deleted-" + hashlib.sha256((user_id + persona.seed).encode()).hexdigest()[:20]
        for vote in db.scalars(select(ViewerVote).where(ViewerVote.viewer_id == user_id)):
            vote.viewer_id = anon
        for contrib in db.scalars(
            select(Contribution).where(Contribution.twitch_user_id == user_id)
        ):
            contrib.twitch_user_id = anon
            contrib.text = "[withdrawn]"
        db.delete(persona)
        return True

    def delete_persona(self, user_id: str) -> bool:
        """Detach identity; keep historic anonymous vote counts and story canon."""
        with self.sessions.begin() as db:
            return self._delete_persona_in_db(db, user_id)

    def list_personas(self, limit: int = 25) -> list[Persona]:
        with self.sessions() as db:
            return list(
                db.scalars(
                    select(Persona)
                    .where(Persona.visible.is_(True))
                    .order_by(Persona.score.desc(), Persona.id)
                    .limit(limit)
                )
            )

    def persona(self, user_id: str) -> Persona | None:
        with self.sessions() as db:
            return db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))

    def create_story(self, title: str, premise: str, tone: str = "mystery") -> int:
        if not 3 <= len(title.strip()) <= 120 or not 15 <= len(premise.strip()) <= 800:
            raise StoryError("Title must be 3–120 and premise 15–800 characters")
        if tone not in {"mystery", "fantasy", "science-fiction", "adventure"}:
            raise StoryError("Unsupported tone")
        with self.sessions.begin() as db:
            current = self._active(db)
            if current and current.stage not in ("FINISHED", "ARCHIVED"):
                raise StoryError("Finish the current story before starting another")
            world = World(title=title.strip(), premise=premise.strip(), tone=tone)
            db.add(world)
            db.flush()
            story = StorySession(
                world_id=world.id, stage="GENERATING", generation_status="AWAITING"
            )
            db.add(story)
            db.flush()
            db.add(AuditEvent(action="story.create", details=title[:120]))
            return story.id

    def mark_generation_started(self) -> None:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "GENERATING":
                raise StoryError("No scene is awaiting generation")
            story.generation_status = "AWAITING"

    def mark_generation_failed(self) -> None:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "GENERATING":
                raise StoryError("No scene generation is active")
            story.generation_status = "FAILED"

    def generator_context(self) -> dict:
        with self.sessions() as db:
            story = self._active(db)
            if not story or story.stage != "GENERATING":
                raise StoryError("No scene is awaiting generation")
            world = db.get(World, story.world_id)
            node = db.get(StoryNode, story.current_node_id) if story.current_node_id else None
            round_ = db.get(VotingRound, story.active_round_id) if story.active_round_id else None
            decision = "enter the story"
            if node and round_ and round_.winning_choice:
                opts = json.loads(round_.options_json)
                decision = opts.get(round_.winning_choice, "continue")
            participants = list(
                db.scalars(select(Persona).where(Persona.visible.is_(True)).limit(8))
            )
            lines = list(
                db.scalars(
                    select(Contribution)
                    .where(Contribution.session_id == story.id, Contribution.status == "APPROVED")
                    .order_by(Contribution.id.desc())
                    .limit(4)
                )
            )
            # Walk only the active canonical ancestry.  This is deterministic,
            # bounded, and preserves alternate branches without sending them to
            # the model as if they were canon.
            chain: list[StoryNode] = []
            cursor = node
            while cursor is not None and len(chain) < 6:
                chain.append(cursor)
                cursor = db.get(StoryNode, cursor.parent_node_id) if cursor.parent_node_id else None
            chain.reverse()
            synopsis: list[str] = []
            for index, chapter in enumerate(chain, start=1):
                narrative = " ".join(chapter.narrative.split())[:520]
                decision_text = ""
                if chapter.parent_node_id and chapter.selected_choice:
                    parent = db.get(StoryNode, chapter.parent_node_id)
                    if parent:
                        parent_choices = json.loads(parent.choices_json)
                        decision_text = parent_choices.get(
                            chapter.selected_choice, chapter.selected_choice
                        )
                suffix = f" Decision: {decision_text[:150]}." if decision_text else ""
                synopsis.append(f"Chapter {index}: {chapter.title}. {narrative}{suffix}")
            canonical_synopsis = "\n".join(synopsis)[-3800:]
            character_context = [
                p.alias + (" (host)" if p.is_host else " (" + p.archetype + ")")
                for p in participants
            ]
            # Keep the public generator contract compact: the bounded synopsis
            # carries prior decisions while the world premise remains explicit.
            return {
                "world": world.premise,
                "history": canonical_synopsis,
                "decision": decision,
                "personas": character_context,
                "contributions": [c.text for c in lines],
            }

    def save_proposal(self, proposal: NarrativeProposal, provenance: str) -> SceneProposal:
        if provenance not in {"AI", "DEMO"}:
            raise StoryError("Invalid provenance")
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "GENERATING":
                raise StoryError("Scene generation is not pending")
            round_ = db.get(VotingRound, story.active_round_id) if story.active_round_id else None
            choices = {chr(65 + i): v for i, v in enumerate(proposal.choices)}
            item = SceneProposal(
                session_id=story.id,
                parent_node_id=story.current_node_id,
                selected_choice=round_.winning_choice if round_ else None,
                title=proposal.title,
                narrative=proposal.narrative,
                choices_json=_json(choices),
                provenance=provenance,
            )
            db.add(item)
            db.flush()
            story.active_proposal_id = item.id
            story.stage = "REVIEW"
            story.generation_status = "AI-GENERATED" if provenance == "AI" else "DEMO-GENERATED"
            return item

    def approve_proposal(self) -> StoryNode:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "REVIEW" or not story.active_proposal_id:
                raise StoryError("There is no proposal awaiting review")
            item = db.get(SceneProposal, story.active_proposal_id)
            if item.status != "PENDING":
                raise StoryError("Proposal already resolved")
            node = StoryNode(
                session_id=story.id,
                parent_node_id=item.parent_node_id,
                selected_choice=item.selected_choice,
                title=item.title,
                narrative=item.narrative,
                choices_json=item.choices_json,
                provenance=item.provenance,
            )
            db.add(node)
            db.flush()
            item.status = "APPROVED"
            # The active canon is the path from the new node to its ancestors.
            # Old scenes remain as alternate branches, never deleted.
            path = {node.id}
            parent_id = node.parent_node_id
            while parent_id:
                parent = db.get(StoryNode, parent_id)
                if not parent or parent.session_id != story.id:
                    raise StoryError("Invalid story ancestor")
                path.add(parent.id)
                parent_id = parent.parent_node_id
            for candidate in db.scalars(select(StoryNode).where(StoryNode.session_id == story.id)):
                candidate.is_canon = candidate.id in path
            story.current_node_id = node.id
            story.active_proposal_id = None
            story.active_round_id = None
            story.stage = "READY"
            db.add(AuditEvent(action="scene.approve", details=node.title[:120]))
            return node

    def start_voting(self) -> VotingRound:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "READY" or not story.current_node_id:
                raise StoryError("Approve a scene before voting")
            if story.active_round_id:
                current = db.get(VotingRound, story.active_round_id)
                if current and current.status == "OPEN":
                    raise StoryError("A voting round is already open")
            existing_open = db.scalar(
                select(VotingRound).where(
                    VotingRound.session_id == story.id, VotingRound.status == "OPEN"
                )
            )
            if existing_open:
                story.active_round_id = existing_open.id
                raise StoryError("A voting round is already open")
            node = db.get(StoryNode, story.current_node_id)
            round_ = VotingRound(
                session_id=story.id, node_id=node.id, options_json=node.choices_json
            )
            db.add(round_)
            db.flush()
            story.active_round_id = round_.id
            story.stage = "VOTING"
            return round_

    def _cast_vote(self, db: Session, story: StorySession, user_id: str, choice: str) -> None:
        if story.stage != "VOTING" or not story.active_round_id:
            raise StoryError("No open voting round")
        round_ = db.get(VotingRound, story.active_round_id)
        if not round_:
            raise StoryError("No open voting round")
        if round_.status != "OPEN" or choice not in json.loads(round_.options_json):
            raise StoryError("Invalid or closed vote")
        vote = db.scalar(
            select(ViewerVote).where(
                ViewerVote.round_id == round_.id, ViewerVote.viewer_id == user_id
            )
        )
        if vote:
            vote.selection = choice
        else:
            db.add(ViewerVote(round_id=round_.id, viewer_id=user_id, selection=choice))

    def vote(self, user_id: str, choice: str) -> None:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story:
                raise StoryError("No story")
            self._cast_vote(db, story, user_id, choice.upper())

    def close_voting(self) -> str:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage != "VOTING" or not story.active_round_id:
                raise StoryError("No active voting round")
            round_ = db.get(VotingRound, story.active_round_id)
            if not round_ or round_.status != "OPEN":
                raise StoryError("Voting round is already closed")
            opts = json.loads(round_.options_json)
            tally = Counter(
                db.scalars(select(ViewerVote.selection).where(ViewerVote.round_id == round_.id))
            )
            # Tie and zero votes resolve deterministically by option order.
            winning = max(opts, key=lambda choice: tally[choice])
            round_.winning_choice = winning
            round_.status = "CLOSED"
            story.stage = "GENERATING"
            story.generation_status = "AWAITING"
            db.add(AuditEvent(action="vote.resolve", details=winning))
            return winning

    def fork_from(self, node_id: int) -> None:
        """Revisit a previously published node and branch without deleting other scenes."""
        with self.sessions.begin() as db:
            story = self._active(db)
            node = db.get(StoryNode, node_id)
            if not story or story.stage != "READY" or not node or node.session_id != story.id:
                raise StoryError("Story must be ready, and fork node must belong to it")
            story.current_node_id = node_id
            story.active_round_id = None
            db.add(AuditEvent(action="story.fork", details=str(node_id)))

    def set_stage(self, stage: str) -> None:
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story:
                raise StoryError("No story")
            if stage == "PAUSED" and story.stage in {"READY", "VOTING"}:
                story.paused_from_stage = story.stage
                story.stage = "PAUSED"
            elif stage == "READY" and story.stage == "PAUSED":
                restored = story.paused_from_stage or "READY"
                if restored == "VOTING":
                    round_ = (
                        db.get(VotingRound, story.active_round_id)
                        if story.active_round_id
                        else None
                    )
                    if not round_ or round_.status != "OPEN":
                        raise StoryError("Cannot resume a closed voting round")
                story.stage = restored
                story.paused_from_stage = None
            elif stage == "FINISHED" and story.stage == "READY":
                story.stage = "FINISHED"
                story.paused_from_stage = None
            elif stage == "FINISHED" and story.stage == "PAUSED":
                restored = story.paused_from_stage or "READY"
                if restored == "VOTING":
                    raise StoryError("Resume and close the open voting round before finishing")
                story.stage = "FINISHED"
                story.paused_from_stage = None
            else:
                raise StoryError("Invalid stage transition")

    def add_contribution(
        self, user_id: str, kind: str, text: str, *, approved: bool = False
    ) -> None:
        if kind not in {"line", "act", "twist"} or not 3 <= len(text.strip()) <= 300:
            raise StoryError("Invalid contribution")
        with self.sessions.begin() as db:
            story = self._active(db)
            if not story or story.stage == "FINISHED":
                raise StoryError("No active story")
            db.add(
                Contribution(
                    session_id=story.id,
                    twitch_user_id=user_id,
                    kind=kind,
                    text=text.strip(),
                    status="APPROVED" if approved else "PENDING",
                )
            )

    def moderate(self, contribution_id: int, approved: bool) -> None:
        with self.sessions.begin() as db:
            c = db.get(Contribution, contribution_id)
            if not c or c.status != "PENDING":
                raise StoryError("Contribution no longer pending")
            c.status = "APPROVED" if approved else "REJECTED"
            if approved:
                p = db.scalar(select(Persona).where(Persona.twitch_user_id == c.twitch_user_id))
                if p:
                    p.score = min(p.score + 1, 10000)

    def process_chat(self, message_id: str, user_id: str, display: str, text: str) -> str:
        """Apply one recognized command once, throttling spam before durable writes."""
        if (
            not isinstance(message_id, str)
            or not isinstance(user_id, str)
            or not isinstance(display, str)
            or not isinstance(text, str)
            or not message_id
            or not user_id
            or len(message_id) > 128
            or len(user_id) > 128
        ):
            return "INVALID"
        raw = text.strip()
        if not raw.startswith("!") or len(raw) > 330:
            return "IGNORED"
        cmd, _, value = raw.partition(" ")
        cmd = cmd.casefold()
        value = value.strip()
        if cmd not in CHAT_COMMANDS:
            return "UNKNOWN"
        if cmd in {"!help", "!profile", "!story", "!recap"}:
            return "HELP" if cmd == "!help" else "INFO"
        with self.sessions.begin() as db:
            if db.get(EventReceipt, message_id):
                return "DUPLICATE"
            now = self._clock()
            rejected_at = self._recent_rejected_events.get(message_id)
            if rejected_at is not None:
                if now - rejected_at <= REJECTED_EVENT_TTL_SECONDS:
                    return "DUPLICATE"
                self._recent_rejected_events.pop(message_id, None)
            previous = self._last_chat_command.get(user_id)
            if previous is not None and now - previous < CHAT_COMMAND_COOLDOWN_SECONDS:
                self._remember_rejected_event(message_id, now)
                return "COOLDOWN"
            db.add(EventReceipt(message_id=message_id))
            self._remember_chat_command(user_id, now)
            if cmd == "!join":
                p = db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))
                if not p:
                    p = Persona(
                        twitch_user_id=user_id,
                        display_name=display[:80],
                        alias=re.sub(r"[^\w -]", "", display)[:40] or "Wanderer",
                        seed=choose_random_seed(),
                    )
                    db.add(p)
                    db.flush()
                    _revision(db, p)
                return "JOINED"
            p = db.scalar(select(Persona).where(Persona.twitch_user_id == user_id))
            if cmd == "!leave":
                return "LEFT" if self._delete_persona_in_db(db, user_id) else "NOT_JOINED"
            if cmd in {"!persona", "!trait", "!avatar"}:
                if not p:
                    return "NOT_JOINED"
                if cmd == "!persona" and value in ARCHETYPES:
                    p.archetype = value
                elif cmd == "!trait" and value in TRAITS:
                    p.trait = value
                elif cmd == "!avatar" and value == "random":
                    p.accessory = ACCESSORIES[(p.revision) % len(ACCESSORIES)]
                elif value:
                    return "INVALID"
                else:
                    return "PROFILE"
                p.revision += 1
                db.flush()
                _revision(db, p)
                return "UPDATED"
            story = self._active(db)
            if not story or story.stage == "FINISHED":
                return "NO_STORY"
            if cmd == "!vote":
                if not p:
                    return "NOT_JOINED"
                try:
                    self._cast_vote(db, story, user_id, value.upper())
                except StoryError:
                    return "INVALID"
                return "VOTED"
            if cmd in {"!line", "!twist", "!act"}:
                if not p:
                    return "NOT_JOINED"
                if not 3 <= len(value) <= 300:
                    return "INVALID"
                now = self._clock()
                previous_contribution = self._last_contribution_command.get(user_id)
                if previous_contribution is not None and now - previous_contribution < 2.0:
                    return "COOLDOWN"
                self._last_contribution_command[user_id] = now
                if len(self._last_contribution_command) > MAX_COOLDOWN_IDENTITIES:
                    oldest = next(iter(self._last_contribution_command))
                    del self._last_contribution_command[oldest]
                db.add(
                    Contribution(
                        session_id=story.id,
                        twitch_user_id=user_id,
                        kind=cmd[1:],
                        text=value,
                        status="PENDING",
                    )
                )
                return "QUEUED"
            return "UNKNOWN"

    def _remember_chat_command(self, user_id: str, at: float) -> None:
        self._last_chat_command[user_id] = at
        if len(self._last_chat_command) > MAX_COOLDOWN_IDENTITIES:
            oldest = next(iter(self._last_chat_command))
            del self._last_chat_command[oldest]

    def _remember_rejected_event(self, message_id: str, at: float) -> None:
        while self._recent_rejected_events:
            _, oldest_at = next(iter(self._recent_rejected_events.items()))
            if at - oldest_at <= REJECTED_EVENT_TTL_SECONDS:
                break
            self._recent_rejected_events.popitem(last=False)
        self._recent_rejected_events[message_id] = at
        self._recent_rejected_events.move_to_end(message_id)
        if len(self._recent_rejected_events) > MAX_RECENT_REJECTED_EVENTS:
            self._recent_rejected_events.popitem(last=False)

    def snapshot(self) -> dict:
        with self.sessions() as db:
            story = self._active(db)
            if not story:
                return {"story": None, "personas": []}
            world = db.get(World, story.world_id)
            node = db.get(StoryNode, story.current_node_id) if story.current_node_id else None
            proposal = (
                db.get(SceneProposal, story.active_proposal_id)
                if story.active_proposal_id
                else None
            )
            round_ = db.get(VotingRound, story.active_round_id) if story.active_round_id else None
            counts = (
                Counter(
                    db.scalars(select(ViewerVote.selection).where(ViewerVote.round_id == round_.id))
                )
                if round_
                else Counter()
            )
            people = list(
                db.scalars(
                    select(Persona)
                    .where(Persona.visible.is_(True))
                    .order_by(Persona.id.desc())
                    .limit(16)
                )
            )
            contribs = list(
                db.scalars(
                    select(Contribution)
                    .where(Contribution.session_id == story.id)
                    .order_by(Contribution.id.desc())
                    .limit(15)
                )
            )
            nodes = list(
                db.scalars(
                    select(StoryNode).where(StoryNode.session_id == story.id).order_by(StoryNode.id)
                )
            )
            return {
                "story": {
                    "id": story.id,
                    "title": world.title,
                    "premise": world.premise,
                    "stage": story.stage,
                    "generation_status": story.generation_status,
                    "round_id": story.active_round_id,
                },
                "node": {
                    "id": node.id,
                    "title": node.title,
                    "narrative": node.narrative,
                    "choices": json.loads(node.choices_json),
                    "provenance": node.provenance,
                }
                if node
                else None,
                "proposal": {
                    "id": proposal.id,
                    "title": proposal.title,
                    "narrative": proposal.narrative,
                    "choices": json.loads(proposal.choices_json),
                    "provenance": proposal.provenance,
                }
                if proposal
                else None,
                "round": {
                    "status": round_.status,
                    "options": json.loads(round_.options_json),
                    "votes": dict(counts),
                    "winner": round_.winning_choice,
                }
                if round_
                else None,
                "personas": people,
                "contributions": contribs,
                "nodes": nodes,
            }
