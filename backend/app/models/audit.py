import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, JSON, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AuditLog(Base):
    """
    Audit trail recording every agent decision, tool execution,
    token usage, and latency.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket_id = Column(String(36), ForeignKey("tickets.id", ondelete="CASCADE"), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    agent_name = Column(String(100), nullable=False)
    model_used = Column(String(100), nullable=False)
    latency_ms = Column(Float, nullable=False, default=0.0)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    details_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    ticket = relationship("Ticket", back_populates="audit_logs")
