"""
AutoCura - Alert ORM Model
"""

from datetime import datetime

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.helpers import utc_now


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(60), default="monitoring_engine")
    timestamp: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
