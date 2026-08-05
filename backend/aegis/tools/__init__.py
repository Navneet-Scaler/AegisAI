"""Importing this package registers every tool onto `registry`, mock and
real: the six synthetic CRM tools, and send_webhook_notification, a
genuine outbound HTTP call to a public sandbox rather than an in-memory
function."""

from aegis.tools import (
    crm,  # noqa: F401
    webhook,  # noqa: F401
)
from aegis.tools.registry import registry

__all__ = ["registry"]
