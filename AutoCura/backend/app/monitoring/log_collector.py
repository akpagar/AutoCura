"""
AutoCura - Log Collector

Builds structured log-entry payloads for monitoring events. Kept
separate from LogService (which persists them) so the shape of a log
record is defined in one place.
"""

from app.utils.helpers import utc_now


class LogCollector:
    @staticmethod
    def generate_system_log(
        source: str,
        level: str,
        message: str,
        service_name: str = "autocura-core",
    ) -> dict:
        return {
            "timestamp": utc_now(),
            "source": source,
            "level": level,
            "message": message,
            "service_name": service_name,
        }
