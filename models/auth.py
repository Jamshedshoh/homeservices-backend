"""
Identity & authentication domain.
"""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    homeowner = "homeowner"
    provider = "provider"
    admin = "admin"
