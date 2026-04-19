from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import admin, auth, jobs, messages, notifications, offers, payments, providers, quotes, ratings, recurring, users
from seed_admin import ensure_admin_user


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_admin_user()
    yield


app = FastAPI(
    title="HomeServices API",
    description=(
        "Marketplace backend connecting homeowners with service providers. "
        "Covers quote generation, job pool, offer/counter-offer negotiation, "
        "booking, messaging, payments, ratings, recurring jobs, and more."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count", "X-Skip", "X-Limit"],
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
app.include_router(admin.router)


@app.get("/", tags=["Root"])
def read_root():
    return {"status": "ok", "service": "HomeServices API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, reload=True)
