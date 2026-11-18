"""
AutoCura - CPU Monitor

Thin wrapper around psutil for CPU utilization. Kept as its own module
(rather than inlined in monitoring_service.py) so each resource has an
independently testable, single-responsibility collector.
"""

import psutil


class CPUMonitor:
    @staticmethod
    def get_metrics() -> float:
        """
        Returns current CPU utilization percentage across all cores.

        `interval=0.1` blocks briefly to get an accurate instantaneous
        reading; callers running this in the async scheduler already run
        it in a worker thread, so this is safe.
        """
        return psutil.cpu_percent(interval=0.1)
