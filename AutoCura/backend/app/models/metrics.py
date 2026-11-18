"""
AutoCura - Metrics ORM Model

Stores each raw monitoring sample collected from the (simulated)
infrastructure: CPU, memory, disk, network, and service status.
"""

from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.helpers import utc_now


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(default=utc_now, index=True)

    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False)
    disk_usage: Mapped[float] = mapped_column(Float, nullable=False)
    network_in: Mapped[float] = mapped_column(Float, default=0.0)
    network_out: Mapped[float] = mapped_column(Float, default=0.0)

    latency: Mapped[float] = mapped_column(Float, default=0.0)
    error_rate: Mapped[float] = mapped_column(Float, default=0.0)

    service_status: Mapped[str] = mapped_column(String(20), default="running")
    hostname: Mapped[str] = mapped_column(String(120), default="localhost")
