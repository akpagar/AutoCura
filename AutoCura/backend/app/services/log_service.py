"""
AutoCura - Log Service

Persists and queries structured log entries (app/models/logs.py::LogEntry).
"""

from sqlalchemy.orm import Session

from app.models.logs import LogEntry


class LogService:
    @staticmethod
    def record_log(
        db: Session,
        source: str,
        level: str,
        message: str,
        service_name: str = "autocura-core",
    ) -> LogEntry:
        log_entry = LogEntry(
            source=source,
            level=level,
            message=message,
            service_name=service_name,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry

    @staticmethod
    def get_logs(
        db: Session,
        service_name: str | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        query = db.query(LogEntry)
        if service_name:
            query = query.filter(LogEntry.service_name == service_name)
        return query.order_by(LogEntry.timestamp.desc()).limit(limit).all()
