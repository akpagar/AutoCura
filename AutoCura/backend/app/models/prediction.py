"""
AutoCura - Prediction and Failure ORM Models
"""

from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.helpers import utc_now


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("metrics.id"), nullable=True)

    failure_probability: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_failure_type: Mapped[str] = mapped_column(String(40), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="LOW")

    timestamp: Mapped[datetime] = mapped_column(default=utc_now, index=True)


class Failure(Base):
    __tablename__ = "failures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    failure_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)

    detected_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)
    predicted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="open")
