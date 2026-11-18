"""
AutoCura - Recovery ORM Model

Records every recovery action attempted by the recovery engine,
including its verification result and duration, for feedback/history.
"""

from datetime import datetime

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.helpers import utc_now


class Recovery(Base):
    __tablename__ = "recovery"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    failure_id: Mapped[int] = mapped_column(ForeignKey("failures.id"), nullable=True)

    action: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[datetime] = mapped_column(default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[str] = mapped_column(String(255), default="")
    recovery_time: Mapped[float] = mapped_column(Float, default=0.0)
