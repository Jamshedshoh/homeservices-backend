from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import domain models so SQLAlchemy registers their metadata before create_all
import models.auth      # noqa: F401
import models.jobs      # noqa: F401
import models.messaging # noqa: F401
import models.finance   # noqa: F401

from databases.auth_db import AuthBase, engine as auth_engine
from databases.finance_db import FinanceBase, engine as finance_engine
from databases.jobs_db import JobsBase, engine as jobs_engine
from databases.messaging_db import MessagingBase, engine as messaging_engine
from routers import auth, jobs, messages, notifications, offers, payments, providers, quotes, ratings, recurring, users

# Create tables in each domain database
AuthBase.metadata.create_all(bind=auth_engine)
JobsBase.metadata.create_all(bind=jobs_engine)
MessagingBase.metadata.create_all(bind=messaging_engine)
FinanceBase.metadata.create_all(bind=finance_engine)

app = FastAPI(
    title="HomeServices API",
    description=(
        "Marketplace backend connecting homeowners with service providers. "
        "Covers quote generation, job pool, offer/counter-offer negotiation, "
        "booking, messaging, payments, ratings, recurring jobs, and more."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(providers.router)
app.include_router(quotes.router)
app.include_router(jobs.router)
app.include_router(offers.router)
app.include_router(messages.router)
app.include_router(payments.router)
app.include_router(ratings.router)
app.include_router(recurring.router)
app.include_router(notifications.router)


@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "service": "HomeServices API"}
