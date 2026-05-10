"""
Finance domain — payments and ratings.
"""
from __future__ import annotations

import enum


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class PaymentMethod(str, enum.Enum):
    card = "card"
    wallet = "wallet"
    upi = "upi"
