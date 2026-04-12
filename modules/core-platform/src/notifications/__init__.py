"""Notification service, preferences, defaults, and event-driven routing.

Public interface:
    from src.notifications import (
        NotificationService,
        NotificationType,
        DEFAULT_NOTIFICATION_TYPES,
        seed_default_preferences,
        build_notifications_router,
        register_event_routing,
        SmtpEmailDelivery,
        NoOpEmailDelivery,
        NoOpSmsDelivery,
    )
"""

from src.notifications.api import build_notifications_router
from src.notifications.defaults import DEFAULT_NOTIFICATION_TYPES, NotificationType
from src.notifications.delivery import NoOpEmailDelivery, NoOpSmsDelivery, SmtpEmailDelivery
from src.notifications.routing import register_event_routing
from src.notifications.seed import seed_default_preferences
from src.notifications.service import NotificationService

__all__ = [
    "DEFAULT_NOTIFICATION_TYPES",
    "NoOpEmailDelivery",
    "NoOpSmsDelivery",
    "NotificationService",
    "NotificationType",
    "SmtpEmailDelivery",
    "build_notifications_router",
    "register_event_routing",
    "seed_default_preferences",
]
