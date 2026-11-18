"""
AutoCura - Decision ORM Model

Not one of the seven tables originally listed in the database design
section, but item 12 of the spec explicitly requires "store every
decision" -- this table is that store. Kept separate from Recovery
(which records the *execution* and its outcome) so a decision that
results in NO_ACTION is still auditable.
"""

from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.helpers import utc_now


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    failure_type: Mapped[str] = mapped_column(String(40), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(default=utc_now, index=True)
