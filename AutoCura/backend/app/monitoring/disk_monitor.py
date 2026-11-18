"""
AutoCura - Disk Monitor
"""

import os

import psutil

# '/' is not a valid disk_usage path on Windows -- os.sep resolves to the
# current drive root ('C:\\' on Windows, '/' on Linux/macOS) so this works
# on both the Windows dev machine and the Linux Docker container.
_DEFAULT_PATH = os.path.abspath(os.sep)


class DiskMonitor:
    @staticmethod
    def get_metrics(path: str = _DEFAULT_PATH) -> dict:
        """Returns total, used, free disk space (GB) and usage percentage."""
        disk = psutil.disk_usage(path)
        return {
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percentage": disk.percent,
        }
