"""
Messaging & notifications domain.
"""
from __future__ import annotations

import enum


class NotificationType(str, enum.Enum):
    new_job = "new_job"
    new_offer = "new_offer"
    offer_accepted = "offer_accepted"
    offer_rejected = "offer_rejected"
    job_booked = "job_booked"
    job_status_update = "job_status_update"
    new_message = "new_message"
    payment_received = "payment_received"
    rating_received = "rating_received"
