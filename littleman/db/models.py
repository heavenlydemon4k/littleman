from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ── Heartbeat system ──────────────────────────────────────────────────────────

class Heartbeat(Base):
    __tablename__ = "heartbeats"

    id = Column(String, primary_key=True)
    fire_at = Column(DateTime(timezone=True), nullable=False)
    reason = Column(Text, nullable=False)
    session_type = Column(String, nullable=False)
    context = Column(JSON, nullable=False, default=dict)
    status = Column(String, nullable=False, default="SCHEDULED")
    spawned_by = Column(String, ForeignKey("heartbeats.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id = Column(String, primary_key=True)
    heartbeat_id = Column(String, ForeignKey("heartbeats.id"), nullable=True)
    directive = Column(JSON, nullable=True)
    tasks_created = Column(Integer, default=0)
    tasks_completed = Column(Integer, default=0)
    bets_placed = Column(Integer, default=0)
    research_calls = Column(Integer, default=0)
    heartbeats_created = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)
    outcome_summary = Column(Text, nullable=True)


# ── Live activity feed ────────────────────────────────────────────────────────

class AgentEvent(Base):
    """A single observable event from a running wake — the live action feed substrate.

    Wakes run in a different process than the API/WebSocket server (scheduler vs uvicorn)
    and SQLite has no pub/sub, so events are delivered through the database: any process
    appends rows; the API tails the table (WAL lets readers see cross-process commits).
    `seq` is a monotonic cursor for tailing.
    """

    __tablename__ = "agent_events"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String, nullable=False, default=lambda: str(uuid4()))
    agent_session_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)  # session_start|stage|reasoning|tool_call|tool_result|session_done
    payload = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Trading state ─────────────────────────────────────────────────────────────

class Position(Base):
    __tablename__ = "positions"

    id = Column(String, primary_key=True)
    market_id = Column(String, nullable=False)
    market_title = Column(Text, nullable=False)
    direction = Column(String, nullable=False)
    size_usdc = Column(Numeric(18, 6), nullable=False)
    entry_price = Column(Numeric(6, 4), nullable=False)
    predicted_probability = Column(Numeric(6, 4), nullable=False)
    strategy_id = Column(String, ForeignKey("strategies.id"), nullable=True)
    status = Column(String, nullable=False, default="OPEN")
    outcome = Column(String, nullable=True)
    pnl = Column(Numeric(18, 6), nullable=True)
    placed_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    external_order_id = Column(String, nullable=True)


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(String, primary_key=True)
    parent_id = Column(String, ForeignKey("strategies.id"), nullable=True)
    node_type = Column(String, nullable=False)
    title = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    metadata_ = Column("metadata", JSON, nullable=False, default=dict)


class Observation(Base):
    __tablename__ = "observations"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    heartbeat_id = Column(String, ForeignKey("heartbeats.id"), nullable=True)
    action_type = Column(String, nullable=False)
    action_detail = Column(JSON, nullable=False)
    rationale = Column(Text, nullable=True)
    predicted_probability = Column(Numeric(6, 4), nullable=True)
    market_price_at_action = Column(Numeric(6, 4), nullable=True)
    outcome = Column(Text, nullable=True)
    actual_probability = Column(Numeric(6, 4), nullable=True)
    pnl = Column(Numeric(18, 6), nullable=True)
    logged_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class CalibrationEntry(Base):
    """A single resolved probabilistic prediction for calibration tracking."""

    __tablename__ = "calibration_entries"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    domain = Column(String, nullable=False, default="default")
    category = Column(String, nullable=True)
    predicted_probability = Column(Numeric(6, 4), nullable=False)
    actual_outcome = Column(Numeric(6, 4), nullable=False)  # 0.0 or 1.0
    context = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=False)


class KBEntry(Base):
    __tablename__ = "kb_entries"

    id = Column(String, primary_key=True)
    topic = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    source_urls = Column(JSON, nullable=False, default=list)
    confidence = Column(String, nullable=False, default="MEDIUM")
    gathered_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    linked_market_ids = Column(JSON, nullable=False, default=list)


class WorldModel(Base):
    __tablename__ = "world_model"

    id = Column(Integer, primary_key=True, default=1)
    wallet_balance_usdc = Column(Numeric(18, 6), nullable=False, default=0)
    available_balance_usdc = Column(Numeric(18, 6), nullable=False, default=0)
    total_pnl = Column(Numeric(18, 6), nullable=False, default=0)
    last_full_scan = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    extended_state = Column(JSON, nullable=False, default=dict)


# ── Chat UI ───────────────────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    messages = relationship("ChatMessage", back_populates="session", order_by="ChatMessage.created_at")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)        # user | assistant | tool
    content = Column(Text, nullable=True)
    thinking = Column(Text, nullable=True)       # extended thinking block
    tool_calls = Column(JSON, nullable=True)     # [{id, name, args}]
    tool_call_id = Column(String, nullable=True) # for tool result messages
    tool_name = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    session = relationship("ChatSession", back_populates="messages")


# ── Operator guidance ─────────────────────────────────────────────────────────

class AgentGuidance(Base):
    __tablename__ = "agent_guidance"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    consumed_at = Column(DateTime(timezone=True), nullable=True)


# ── Mental construct (DB-backed source of truth) ───────────────────────────────

class ConstructDoc(Base):
    """A single mental construct document stored in the database.

    Files under workspace/construct/ remain as rendered, human-readable mirrors of these rows.
    The DB is the source of truth so concurrent reads/writes are coherent and versioned history
    is possible without locking markdown files.
    """

    __tablename__ = "construct_docs"

    name = Column(String, primary_key=True)            # e.g. PRIORITIES.md
    content = Column(Text, nullable=False, default="")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ── Operator profile / onboarding ─────────────────────────────────────────────

class Profile(Base):
    """Single-row operator profile + onboarding state (id is always 1)."""

    __tablename__ = "profile"

    id = Column(Integer, primary_key=True, default=1)
    display_name = Column(String, nullable=True)
    purpose = Column(Text, nullable=True)              # the agent's prime directive
    onboarding_path = Column(String, nullable=True)    # "guided" | "custom"
    answers = Column(JSON, nullable=True)              # full guided questionnaire answers
    onboarded_at = Column(DateTime(timezone=True), nullable=True)  # null = not yet onboarded
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
