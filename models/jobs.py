"""
Marketplace / jobs domain.
"""
from __future__ import annotations

import enum


class ServiceCategory(str, enum.Enum):
    plumbing = "plumbing"
    electrical = "electrical"
    cleaning = "cleaning"
    painting = "painting"
    carpentry = "carpentry"
    landscaping = "landscaping"
    hvac = "hvac"
    pest_control = "pest_control"
    appliance_repair = "appliance_repair"
    other = "other"


class JobStatus(str, enum.Enum):
    draft = "draft"
    open = "open"
    negotiating = "negotiating"
    booked = "booked"
    en_route = "en_route"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class OfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    countered = "countered"
    withdrawn = "withdrawn"


class RecurrenceFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    biweekly = "biweekly"
    monthly = "monthly"
