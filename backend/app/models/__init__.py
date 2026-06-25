"""SQLAlchemy models for the Smart WiFi Dashboard.

All models are imported here so that Alembic can discover them
when generating migrations.
"""

from app.models.base import Base
from app.models.tenant import Tenant
from app.models.admin import Admin
from app.models.router_config import RouterConfig
from app.models.device import Device
from app.models.blocking_scenario import BlockingScenario
from app.models.firewall_rule import FirewallRule
from app.models.bandwidth_config import BandwidthConfig
from app.models.queue_rule import QueueRule
from app.models.traffic_data import TrafficData
from app.models.anomaly_alert import AnomalyAlert
from app.models.device_session import DeviceSession
from app.models.report import Report
from app.models.audit_log import AuditLog
from app.models.login_attempt import LoginAttempt

__all__ = [
    "Base",
    "Tenant",
    "Admin",
    "RouterConfig",
    "Device",
    "BlockingScenario",
    "FirewallRule",
    "BandwidthConfig",
    "QueueRule",
    "TrafficData",
    "AnomalyAlert",
    "DeviceSession",
    "Report",
    "AuditLog",
    "LoginAttempt",
]
