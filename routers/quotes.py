"""
Self-serve quote generator.
Uses base rates per category + hours + optional complexity adjustments.
Domain: auth only (for current_user — no DB writes)
"""
from fastapi import APIRouter, Depends

from auth import require_homeowner
from models.jobs import ServiceCategory
from schemas import QuoteRequest, QuoteResponse

router = APIRouter(prefix="/quotes", tags=["Quotes"])

# Base hourly rates (USD) — replace with DB-backed pricing table in production
BASE_RATES: dict[ServiceCategory, float] = {
    ServiceCategory.plumbing: 85,
    ServiceCategory.electrical: 95,
    ServiceCategory.cleaning: 45,
    ServiceCategory.painting: 55,
    ServiceCategory.carpentry: 75,
    ServiceCategory.landscaping: 50,
    ServiceCategory.hvac: 110,
    ServiceCategory.pest_control: 60,
    ServiceCategory.appliance_repair: 80,
    ServiceCategory.other: 65,
}

PLATFORM_FEE_RATE = 0.10
MATERIAL_ESTIMATE_RATE = 0.15


@router.post("/generate", response_model=QuoteResponse)
def generate_quote(
    payload: QuoteRequest,
    current_user: dict = Depends(require_homeowner),
):
    base_rate = BASE_RATES.get(payload.service_category, 65)
    labour = round(base_rate * payload.estimated_hours, 2)
    materials = round(labour * MATERIAL_ESTIMATE_RATE, 2)
    platform_fee = round((labour + materials) * PLATFORM_FEE_RATE, 2)
    total = round(labour + materials + platform_fee, 2)

    return QuoteResponse(
        estimated_price=total,
        price_breakdown={
            "labour": labour,
            "materials_estimate": materials,
            "platform_fee": platform_fee,
        },
        service_category=payload.service_category,
        estimated_hours=payload.estimated_hours,
        notes=(
            f"Rate based on average {payload.service_category.value} pricing. "
            "Final price may vary after provider assessment."
        ),
    )
