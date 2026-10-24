"""All tables. Importing this package registers every model on Base.metadata (Alembic, tests)."""

from app.db.models.common import RevCounter, SyncedMixin
from app.db.models.devices import Device, DeviceToken
from app.db.models.logs import AuditLog, ConflictLog, JobLog
from app.db.models.notifications import AlarmFiring, Delivery, Notification
from app.db.models.secrets import Secret
from app.db.models.system import AdminSession, SystemSetting
from app.db.models.users import User, UserSettings

__all__ = [
    "AdminSession",
    "AlarmFiring",
    "AuditLog",
    "ConflictLog",
    "Delivery",
    "Device",
    "DeviceToken",
    "JobLog",
    "Notification",
    "RevCounter",
    "Secret",
    "SyncedMixin",
    "SystemSetting",
    "User",
    "UserSettings",
]
