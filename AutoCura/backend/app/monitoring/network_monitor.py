"""
AutoCura - Network Monitor
"""

import psutil


class NetworkMonitor:
    @staticmethod
    def get_metrics() -> dict:
        """
        Returns cumulative bytes/packets sent and received since boot.

        These are cumulative counters, not a rate -- the dashboard/ML
        layer should difference consecutive samples if a per-interval
        throughput figure is needed.
        """
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
        }
