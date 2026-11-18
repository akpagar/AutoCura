"""
AutoCura - Memory Monitor
"""

import psutil


class MemoryMonitor:
    @staticmethod
    def get_metrics() -> dict:
        """Returns total, used, available memory (GB) and usage percentage."""
        mem = psutil.virtual_memory()
        return {
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
            "percentage": mem.percent,
        }
