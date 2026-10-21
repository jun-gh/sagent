import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    TRIAGED = "TRIAGED"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"


class TicketUrgency(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TicketCategory(str, enum.Enum):
    TECHNICAL = "TECHNICAL"
    BILLING = "BILLING"
    AUTH = "AUTH"
    FEATURE_REQUEST = "FEATURE_REQUEST"
    SECURITY = "SECURITY"
    GENERAL = "GENERAL"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=False)
    customer_email = Column(String(255), nullable=True)
    customer_tier = Column(String(50), default="standard")  # standard, premium, enterprise
    session_id = Column(String(64), nullable=True, index=True)  # Anonymous session scoping
    
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.OPEN, nullable=False, index=True)
    urgency = Column(SQLEnum(TicketUrgency), default=TicketUrgency.MEDIUM, nullable=False, index=True)
    category = Column(SQLEnum(TicketCategory), default=TicketCategory.GENERAL, nullable=False, index=True)
    
    # AI Triage outputs
    sentiment = Column(String(50), nullable=True)
    confidence_score = Column(String(10), nullable=True)
    suggested_reply = Column(Text, nullable=True)
    internal_action_plan = Column(JSON, nullable=True)  # List of action steps
    tags = Column(JSON, nullable=True)  # List of string tags
    triage_notes = Column(Text, nullable=True)
    grounding_citations = Column(JSON, nullable=True)  # List of citation dicts
    agent_steps = Column(JSON, nullable=True)  # List of agent reasoning steps
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    audit_logs = relationship("AuditLog", back_populates="ticket", cascade="all, delete-orphan")
