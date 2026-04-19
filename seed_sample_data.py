"""
Load each domain table with ~5 rows of coherent sample data (dev / demos).

Wipes ALL rows in auth, jobs, finance, and messaging databases when run with
--force. Cross-database references use matching integer IDs (users, jobs, etc.).

Usage:
  python seed_sample_data.py --force

Requires dependencies from requirements.txt (same venv as the API).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from auth import hash_password
from config import settings
from databases.auth_db import SessionLocal as AuthSessionLocal
from databases.finance_db import SessionLocal as FinanceSessionLocal
from databases.jobs_db import SessionLocal as JobsSessionLocal
from databases.messaging_db import SessionLocal as MessagingSessionLocal
from models.auth import User, UserRole
from models.finance import Payment, PaymentMethod, PaymentStatus, Rating
from models.jobs import (
    Job,
    JobStatus,
    JobTemplate,
    Offer,
    OfferStatus,
    RecurrenceFrequency,
    ServiceCategory,
)
from models.messaging import Message, Notification, NotificationType

SAMPLE_PASSWORD = "SampleSeed#2024"


def wipe_all() -> None:
    md = MessagingSessionLocal()
    try:
        md.query(Message).delete()
        md.query(Notification).delete()
        md.commit()
    finally:
        md.close()

    fd = FinanceSessionLocal()
    try:
        fd.query(Rating).delete()
        fd.query(Payment).delete()
        fd.commit()
    finally:
        fd.close()

    jd = JobsSessionLocal()
    try:
        jd.query(Offer).delete()
        jd.query(Job).delete()
        jd.query(JobTemplate).delete()
        jd.commit()
    finally:
        jd.close()

    ad = AuthSessionLocal()
    try:
        ad.query(User).delete()
        ad.commit()
    finally:
        ad.close()


def seed() -> None:
    now = datetime.now(timezone.utc)
    hp = hash_password(SAMPLE_PASSWORD)

    ad = AuthSessionLocal()
    try:
        users = [
            User(
                id=1,
                email="admin@sample.local",
                hashed_password=hp,
                full_name="Sample Admin",
                phone="555-0100",
                role=UserRole.admin.value,
                is_active=True,
                address=None,
            ),
            User(
                id=2,
                email="alice.home@sample.local",
                hashed_password=hp,
                full_name="Alice Chen",
                phone="555-0101",
                role=UserRole.homeowner.value,
                is_active=True,
                address="120 Oak St, Springfield",
            ),
            User(
                id=3,
                email="bob.home@sample.local",
                hashed_password=hp,
                full_name="Bob Martinez",
                phone="555-0102",
                role=UserRole.homeowner.value,
                is_active=True,
                address="45 Pine Ave, Springfield",
            ),
            User(
                id=4,
                email="carla.pro@sample.local",
                hashed_password=hp,
                full_name="Carla Nguyen",
                phone="555-0103",
                role=UserRole.provider.value,
                is_active=True,
                bio="Licensed plumber & electrician, 10+ years.",
                service_categories="plumbing,electrical",
                hourly_rate=85.0,
                latitude=42.36,
                longitude=-71.06,
                service_radius_km=30.0,
            ),
            User(
                id=5,
                email="derek.pro@sample.local",
                hashed_password=hp,
                full_name="Derek Walsh",
                phone="555-0104",
                role=UserRole.provider.value,
                is_active=True,
                bio="Cleaning & painting specialist.",
                service_categories="cleaning,painting",
                hourly_rate=55.0,
                latitude=42.35,
                longitude=-71.05,
                service_radius_km=25.0,
            ),
        ]
        ad.add_all(users)
        ad.commit()
    finally:
        ad.close()

    jd = JobsSessionLocal()
    try:
        templates = [
            JobTemplate(
                id=1,
                homeowner_id=2,
                name="Monthly deep clean",
                service_category=ServiceCategory.cleaning,
                description="Kitchen, bathrooms, floors — recurring monthly.",
                address="120 Oak St, Springfield",
                estimated_hours=4.0,
                base_quote=220.0,
                is_recurring=True,
                recurrence_frequency=RecurrenceFrequency.monthly,
                next_scheduled_at=now + timedelta(days=14),
            ),
            JobTemplate(
                id=2,
                homeowner_id=2,
                name="Leak under sink",
                service_category=ServiceCategory.plumbing,
                description="Persistent drip; need inspection and repair quote.",
                address="120 Oak St, Springfield",
                estimated_hours=2.0,
                base_quote=180.0,
                is_recurring=False,
            ),
            JobTemplate(
                id=3,
                homeowner_id=3,
                name="Exterior paint touch-up",
                service_category=ServiceCategory.painting,
                description="Trim and south-facing siding refresh.",
                address="45 Pine Ave, Springfield",
                estimated_hours=6.0,
                base_quote=900.0,
                is_recurring=False,
            ),
            JobTemplate(
                id=4,
                homeowner_id=3,
                name="Lawn & hedge",
                service_category=ServiceCategory.landscaping,
                description="Biweekly mowing and seasonal hedge trim.",
                address="45 Pine Ave, Springfield",
                estimated_hours=3.0,
                base_quote=150.0,
                is_recurring=True,
                recurrence_frequency=RecurrenceFrequency.biweekly,
                next_scheduled_at=now + timedelta(days=7),
            ),
            JobTemplate(
                id=5,
                homeowner_id=2,
                name="Outlet replacement",
                service_category=ServiceCategory.electrical,
                description="Replace two GFCI outlets in garage.",
                address="120 Oak St, Springfield",
                estimated_hours=1.5,
                base_quote=200.0,
                is_recurring=False,
            ),
        ]
        jd.add_all(templates)

        jobs = [
            Job(
                id=1,
                homeowner_id=2,
                provider_id=None,
                title="Kitchen faucet leak",
                description="Steady leak under kitchen sink; need repair this week.",
                service_category=ServiceCategory.plumbing,
                status=JobStatus.open,
                address="120 Oak St, Springfield",
                latitude=42.36,
                longitude=-71.06,
                estimated_hours=2.0,
                homeowner_quote=200.0,
                final_price=None,
                preferred_date=now + timedelta(days=3),
                scheduled_at=None,
                template_id=2,
            ),
            Job(
                id=2,
                homeowner_id=2,
                provider_id=4,
                title="Panel upgrade estimate",
                description="200A panel upgrade; need quote and timeline.",
                service_category=ServiceCategory.electrical,
                status=JobStatus.negotiating,
                address="120 Oak St, Springfield",
                estimated_hours=8.0,
                homeowner_quote=2400.0,
                final_price=None,
                preferred_date=now + timedelta(days=10),
                template_id=5,
            ),
            Job(
                id=3,
                homeowner_id=3,
                provider_id=5,
                title="Move-out clean",
                description="Full apartment clean before handover.",
                service_category=ServiceCategory.cleaning,
                status=JobStatus.booked,
                address="45 Pine Ave, Springfield",
                estimated_hours=5.0,
                homeowner_quote=350.0,
                final_price=340.0,
                preferred_date=now + timedelta(days=5),
                scheduled_at=now + timedelta(days=5, hours=2),
                template_id=1,
            ),
            Job(
                id=4,
                homeowner_id=2,
                provider_id=4,
                title="Deck board replacement",
                description="Replace rotted boards on rear deck.",
                service_category=ServiceCategory.carpentry,
                status=JobStatus.completed,
                address="120 Oak St, Springfield",
                estimated_hours=6.0,
                homeowner_quote=800.0,
                final_price=780.0,
                scheduled_at=now - timedelta(days=3),
                template_id=None,
            ),
            Job(
                id=5,
                homeowner_id=3,
                provider_id=5,
                title="Interior room paint",
                description="Two bedrooms, ceilings included.",
                service_category=ServiceCategory.painting,
                status=JobStatus.completed,
                address="45 Pine Ave, Springfield",
                estimated_hours=12.0,
                homeowner_quote=1400.0,
                final_price=1350.0,
                scheduled_at=now - timedelta(days=10),
                template_id=3,
            ),
        ]
        jd.add_all(jobs)

        offers = [
            Offer(
                id=1,
                job_id=1,
                provider_id=4,
                proposed_price=195.0,
                message="Can come Tuesday afternoon.",
                status=OfferStatus.pending,
            ),
            Offer(
                id=2,
                job_id=1,
                provider_id=5,
                proposed_price=210.0,
                message="Includes parts estimate.",
                status=OfferStatus.rejected,
            ),
            Offer(
                id=3,
                job_id=2,
                provider_id=4,
                proposed_price=2300.0,
                message="Materials extra; 2-day job.",
                status=OfferStatus.countered,
            ),
            Offer(
                id=4,
                job_id=3,
                provider_id=5,
                proposed_price=340.0,
                message="Confirmed for your slot.",
                status=OfferStatus.accepted,
            ),
            Offer(
                id=5,
                job_id=4,
                provider_id=4,
                proposed_price=780.0,
                message="Completed as quoted.",
                status=OfferStatus.accepted,
            ),
        ]
        jd.add_all(offers)
        jd.commit()
    finally:
        jd.close()

    fd = FinanceSessionLocal()
    try:
        payments = [
            Payment(
                id=1,
                job_id=1,
                homeowner_id=2,
                provider_id=4,
                amount=195.0,
                method=PaymentMethod.card,
                status=PaymentStatus.pending,
                transaction_ref=None,
                completed_at=None,
            ),
            Payment(
                id=2,
                job_id=2,
                homeowner_id=2,
                provider_id=4,
                amount=2300.0,
                method=PaymentMethod.wallet,
                status=PaymentStatus.processing,
                transaction_ref="txn_w_1001",
                completed_at=None,
            ),
            Payment(
                id=3,
                job_id=3,
                homeowner_id=3,
                provider_id=5,
                amount=340.0,
                method=PaymentMethod.upi,
                status=PaymentStatus.completed,
                transaction_ref="upi_9001",
                completed_at=now - timedelta(days=4),
            ),
            Payment(
                id=4,
                job_id=4,
                homeowner_id=2,
                provider_id=4,
                amount=780.0,
                method=PaymentMethod.card,
                status=PaymentStatus.completed,
                transaction_ref="ch_7x2k9",
                completed_at=now - timedelta(days=2),
            ),
            Payment(
                id=5,
                job_id=5,
                homeowner_id=3,
                provider_id=5,
                amount=1350.0,
                method=PaymentMethod.card,
                status=PaymentStatus.refunded,
                transaction_ref="ch_refund_3",
                completed_at=now - timedelta(days=8),
            ),
        ]
        fd.add_all(payments)

        ratings = [
            Rating(id=1, job_id=1, rater_id=2, ratee_id=4, score=4, comment="Responsive quote."),
            Rating(id=2, job_id=2, rater_id=2, ratee_id=4, score=5, comment="Clear communication."),
            Rating(id=3, job_id=3, rater_id=3, ratee_id=5, score=5, comment="Spotless work."),
            Rating(id=4, job_id=4, rater_id=2, ratee_id=4, score=5, comment="Deck looks great."),
            Rating(id=5, job_id=5, rater_id=3, ratee_id=5, score=4, comment="Minor paint smell; otherwise perfect."),
        ]
        fd.add_all(ratings)
        fd.commit()
    finally:
        fd.close()

    md = MessagingSessionLocal()
    try:
        messages = [
            Message(
                id=1,
                job_id=1,
                sender_id=2,
                recipient_id=4,
                content="Are you available Tuesday for the faucet job?",
                is_read=True,
            ),
            Message(
                id=2,
                job_id=1,
                sender_id=4,
                recipient_id=2,
                content="Yes — I can do 2–4pm. I'll bring standard washers.",
                is_read=True,
            ),
            Message(
                id=3,
                job_id=2,
                sender_id=4,
                recipient_id=2,
                content="Panel upgrade needs permit photos; sending checklist.",
                is_read=False,
            ),
            Message(
                id=4,
                job_id=3,
                sender_id=3,
                recipient_id=5,
                content="Please bring green cleaning supplies only.",
                is_read=True,
            ),
            Message(
                id=5,
                job_id=4,
                sender_id=2,
                recipient_id=4,
                content="Thanks for finishing the deck ahead of schedule!",
                is_read=True,
            ),
        ]
        md.add_all(messages)

        notifications = [
            Notification(
                id=1,
                user_id=2,
                type=NotificationType.new_offer,
                title="New offer on your job",
                body="Carla proposed $195 for Kitchen faucet leak.",
                is_read=False,
                job_id=1,
                offer_id=1,
            ),
            Notification(
                id=2,
                user_id=4,
                type=NotificationType.new_message,
                title="New message",
                body="Alice sent you a message about job #1.",
                is_read=True,
                job_id=1,
                offer_id=None,
            ),
            Notification(
                id=3,
                user_id=3,
                type=NotificationType.job_booked,
                title="Job booked",
                body="Move-out clean is scheduled.",
                is_read=False,
                job_id=3,
                offer_id=4,
            ),
            Notification(
                id=4,
                user_id=5,
                type=NotificationType.payment_received,
                title="Payment completed",
                body="You received $340.00 for job #3.",
                is_read=True,
                job_id=3,
                offer_id=None,
            ),
            Notification(
                id=5,
                user_id=2,
                type=NotificationType.rating_received,
                title="New rating",
                body="Derek left you feedback.",
                is_read=False,
                job_id=5,
                offer_id=None,
            ),
        ]
        md.add_all(notifications)
        md.commit()
    finally:
        md.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed sample data into all domain SQLite DBs.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing rows in all app tables, then insert sample rows (destructive).",
    )
    args = parser.parse_args()

    if not args.force:
        print("Refusing to run without --force (this deletes existing data).")
        print("  python seed_sample_data.py --force")
        raise SystemExit(1)

    print(f"Databases: auth={settings.auth_database_url} …")
    wipe_all()
    seed()
    print("Done. Sample login (all users):", SAMPLE_PASSWORD)
    print("  admin@sample.local, alice.home@sample.local, bob.home@sample.local,")
    print("  carla.pro@sample.local, derek.pro@sample.local")


if __name__ == "__main__":
    main()
