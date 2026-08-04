"""Importing this package registers every mock CRM tool onto `registry`."""

from aegis.tools import crm  # noqa: F401
from aegis.tools.registry import registry

__all__ = ["registry"]
