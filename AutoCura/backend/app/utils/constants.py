"""
AutoCura - Shared Constants and Enumerations

Centralizes fixed vocabularies (failure types, severities, actions, statuses)
so every module (ML, decision engine, recovery, API schemas) agrees on the
same set of values.
"""

from enum import StrEnum


class FailureType(StrEnum):
    NORMAL = "normal"
    CPU_OVERLOAD = "cpu_overload"
    MEMORY_EXHAUSTION = "memory_exhaustion"
    DISK_EXHAUSTION = "disk_exhaustion"
    SERVICE_FAILURE = "service_failure"
    NETWORK_DEGRADATION = "network_degradation"
    HIGH_ERROR_RATE = "high_error_rate"
    SERVICE_DEGRADED = "service_degraded"
    RESOURCE_SATURATION = "resource_saturation"


class Severity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RecoveryAction(StrEnum):
    RESTART_SERVICE = "restart_service"
    SCALE_SERVICE = "scale_service"
    REDISTRIBUTE_WORKLOAD = "redistribute_workload"
    CLEANUP_DISK = "cleanup_disk"
    SCALE_AND_RESTART = "scale_and_restart"
    NO_ACTION = "no_action"


class RecoveryStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ESCALATED = "escalated"


class ServiceStatus(StrEnum):
    RUNNING = "running"
    DEGRADED = "degraded"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class UserRole(StrEnum):
    ADMIN = "admin"
    VIEWER = "viewer"
