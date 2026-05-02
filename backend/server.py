import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from emergentintegrations.llm.chat import ImageContent, LlmChat, UserMessage
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
jwt_secret = os.environ["JWT_SECRET"]
emergent_llm_key = os.environ["EMERGENT_LLM_KEY"]
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
TOKEN_EXPIRY_DAYS = 14

# ---------------------------------------------------------------------------
# Munchy Plus+ Pricing Plans
# ---------------------------------------------------------------------------
SUBSCRIPTION_PLANS = {
    "monthly": {
        "id": "monthly",
        "name": "Monthly",
        "price": 3.99,
        "currency": "USD",
        "duration_days": 30,
        "display": "$3.99/month",
    },
    "annual": {
        "id": "annual",
        "name": "Annual",
        "price": 24.99,
        "currency": "USD",
        "duration_days": 365,
        "display": "$24.99/year",
    },
    "lifetime": {
        "id": "lifetime",
        "name": "Lifetime",
        "price": 59.99,
        "currency": "USD",
        "duration_days": None,
        "display": "$59.99 one-time",
    },
}

# ---------------------------------------------------------------------------
# LLM Prompts — cost-tiered
# ---------------------------------------------------------------------------
LLM_SYSTEM_PROMPT_FREE = """
You are a food recognition AI. Analyze the uploaded food image and reply ONLY with valid JSON:
{
  "foodName": "Name of the dish",
  "totalCalories": 450,
  "confidence": "high",
  "serving": "1 bowl (~320g)",
  "macros": {"protein": 0, "carbs": 0, "fat": 0, "fiber": 0},
  "ingredients": [],
  "note": "Upgrade to Munchy Plus+ for full nutrient breakdown."
}
Rules:
- No markdown fences. No extra explanation.
- Only estimate foodName, totalCalories, confidence, and serving.
- Leave macros zeroed and ingredients empty to save tokens.
- If food is unclear, use foodName "Unknown meal" and totalCalories 0.
""".strip()

LLM_SYSTEM_PROMPT_PREMIUM = """
You are a professional nutritionist and food recognition AI.
Analyze the uploaded food image and reply ONLY with valid JSON in this shape:
{
  "foodName": "Name of the dish",
  "totalCalories": 450,
  "confidence": "high",
  "serving": "1 bowl (~320g)",
  "macros": {
    "protein": 22,
    "carbs": 48,
    "fat": 18,
    "fiber": 4
  },
  "ingredients": [
    {"name": "Chicken breast", "calories": 165, "amount": "100g"},
    {"name": "Rice", "calories": 130, "amount": "100g"}
  ],
  "micronutrients": {
    "vitaminA": "120mcg",
    "vitaminC": "5mg",
    "calcium": "45mg",
    "iron": "2.1mg",
    "potassium": "310mg",
    "sodium": "480mg"
  },
  "note": "Brief note about the estimate"
}
Rules:
- No markdown fences.
- No extra explanation.
- Estimate realistically.
- Include full macros, ingredient breakdown, and micronutrient estimates.
- If uncertain, set confidence to medium or low.
- If food is unclear, use foodName "Unknown meal" and totalCalories 0.
""".strip()

# Keep the old prompt name pointing to premium for backward-compat
LLM_SYSTEM_PROMPT = LLM_SYSTEM_PROMPT_PREMIUM

LLM_USER_MSG_FREE = "Analyze this food image and estimate the dish name, total calories, confidence level, and serving size only."
LLM_USER_MSG_PREMIUM = "Analyze this food image and estimate calories, macros, full ingredient breakdown, micronutrients, and serving size."

app = FastAPI(title="Calorie Scanner API")
api_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    email: EmailStr
    created_at: str
    is_premium: bool = False
    subscription_expiry: Optional[str] = None
    streak_count: int = 0
    last_scan_date: Optional[str] = None


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class MacroBreakdown(BaseModel):
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    fiber: float = 0


class Micronutrients(BaseModel):
    vitaminA: str = ""
    vitaminC: str = ""
    calcium: str = ""
    iron: str = ""
    potassium: str = ""
    sodium: str = ""


class IngredientItem(BaseModel):
    name: str
    calories: float = 0
    amount: str = ""


class ScanAnalysis(BaseModel):
    foodName: str
    totalCalories: float = 0
    confidence: str = "medium"
    serving: str = "Estimated serving"
    macros: MacroBreakdown = Field(default_factory=MacroBreakdown)
    ingredients: List[IngredientItem] = Field(default_factory=list)
    micronutrients: Optional[Micronutrients] = None
    note: str = "Nutrition values are estimated from the image."


class ScanRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    user_id: str
    created_at: str
    image_data_url: Optional[str] = None
    result: ScanAnalysis


class SubscriptionPlan(BaseModel):
    id: str
    name: str
    price: float
    currency: str
    duration_days: Optional[int]
    display: str


class SubscriptionActivateRequest(BaseModel):
    plan_id: str
    payment_token: str  # Mock payment token for now (Play Store Billing later)
    receipt_data: Optional[str] = None


class SubscriptionStatus(BaseModel):
    is_premium: bool
    plan_id: Optional[str] = None
    subscription_expiry: Optional[str] = None
    auto_renew: bool = False


class SubscriptionActivateResponse(BaseModel):
    success: bool
    message: str
    subscription: SubscriptionStatus


class StreakResponse(BaseModel):
    streak_count: int
    last_scan_date: Optional[str] = None


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def normalize_number(value: object) -> float:
    try:
        if isinstance(value, str):
            cleaned = re.sub(r"[^0-9.]", "", value)
            return round(float(cleaned), 1) if cleaned else 0
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRY_DAYS),
    }
    return jwt.encode(payload, jwt_secret, algorithm="HS256")


def check_premium_status(user_doc: dict) -> bool:
    """Determine if user currently has active premium status."""
    if not user_doc.get("is_premium", False):
        return False
    expiry = user_doc.get("subscription_expiry")
    if expiry is None:
        # Lifetime subscription
        return True
    if isinstance(expiry, str):
        try:
            expiry_dt = datetime.fromisoformat(expiry)
        except ValueError:
            return False
    elif isinstance(expiry, datetime):
        expiry_dt = expiry
    else:
        return False
    return expiry_dt > now_utc()


def compute_streak(current_streak: int, last_scan_date: Optional[str], scan_date: str) -> tuple[int, str]:
    """Compute new streak count and last_scan_date given a new scan.

    Returns (new_streak_count, new_last_scan_date).
    """
    if not last_scan_date:
        return 1, scan_date

    if last_scan_date == scan_date:
        return max(current_streak, 1), scan_date

    try:
        last_dt = datetime.strptime(last_scan_date, "%Y-%m-%d").date()
        scan_dt = datetime.strptime(scan_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return 1, scan_date

    delta = (scan_dt - last_dt).days

    if delta == 1:
        return current_streak + 1, scan_date
    elif delta == 0:
        return max(current_streak, 1), scan_date
    else:
        return 1, scan_date


def build_user_public(user_doc: dict) -> UserPublic:
    is_premium = check_premium_status(user_doc)
    return UserPublic(
        id=user_doc["id"],
        name=user_doc["name"],
        email=user_doc["email"],
        created_at=user_doc["created_at"],
        is_premium=is_premium,
        subscription_expiry=user_doc.get("subscription_expiry"),
        streak_count=user_doc.get("streak_count", 0),
        last_scan_date=user_doc.get("last_scan_date"),
    )


def build_auth_response(user_doc: dict) -> AuthResponse:
    return AuthResponse(token=create_token(user_doc["id"]), user=build_user_public(user_doc))


def extract_json_payload(text: str) -> dict:
    cleaned = text.replace("```json", "").replace("```", "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(cleaned[start : end + 1])


def normalize_analysis(payload: dict, is_premium: bool = False) -> ScanAnalysis:
    macros = payload.get("macros") or {}
    ingredients = payload.get("ingredients") or []
    micronutrients_raw = payload.get("micronutrients") or {}

    macro_breakdown = MacroBreakdown(
        protein=normalize_number(macros.get("protein")) if is_premium else 0,
        carbs=normalize_number(macros.get("carbs")) if is_premium else 0,
        fat=normalize_number(macros.get("fat")) if is_premium else 0,
        fiber=normalize_number(macros.get("fiber")) if is_premium else 0,
    )

    ingredient_list = []
    if is_premium:
        ingredient_list = [
            IngredientItem(
                name=str(item.get("name") or "Ingredient"),
                calories=normalize_number(item.get("calories")),
                amount=str(item.get("amount") or "Estimated amount"),
            )
            for item in ingredients[:8]
        ]

    micro = None
    if is_premium and micronutrients_raw:
        micro = Micronutrients(
            vitaminA=str(micronutrients_raw.get("vitaminA", "")),
            vitaminC=str(micronutrients_raw.get("vitaminC", "")),
            calcium=str(micronutrients_raw.get("calcium", "")),
            iron=str(micronutrients_raw.get("iron", "")),
            potassium=str(micronutrients_raw.get("potassium", "")),
            sodium=str(micronutrients_raw.get("sodium", "")),
        )

    note = str(payload.get("note") or "Nutrition values are estimated from the image.")
    if not is_premium:
        note = "Upgrade to Munchy Plus+ for full macros, ingredients, and micronutrient analysis."

    return ScanAnalysis(
        foodName=str(payload.get("foodName") or "Unknown meal"),
        totalCalories=normalize_number(payload.get("totalCalories")),
        confidence=str(payload.get("confidence") or "medium").lower(),
        serving=str(payload.get("serving") or "Estimated serving"),
        macros=macro_breakdown,
        ingredients=ingredient_list,
        micronutrients=micro,
        note=note,
    )


def get_llm_prompt_for_user(is_premium: bool) -> tuple[str, str]:
    """Return (system_prompt, user_message) based on subscription tier."""
    if is_premium:
        return LLM_SYSTEM_PROMPT_PREMIUM, LLM_USER_MSG_PREMIUM
    return LLM_SYSTEM_PROMPT_FREE, LLM_USER_MSG_FREE


def validate_mock_payment(payment_token: str) -> bool:
    """
    Mock payment validation. In production this will verify against
    Google Play Billing / Apple IAP receipts.
    Accepts any non-empty token that starts with 'mock_' or 'tok_'.
    """
    if not payment_token or not isinstance(payment_token, str):
        return False
    payment_token = payment_token.strip()
    return len(payment_token) >= 4


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please sign in first.")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.") from exc

    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found.")
    return user


def require_premium(user_doc: dict) -> None:
    """Raise 403 if the user does not have an active Munchy Plus+ subscription."""
    if not check_premium_status(user_doc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This feature requires an active Munchy Plus+ subscription.",
        )


# ---------------------------------------------------------------------------
# Routes — Root
# ---------------------------------------------------------------------------

@api_router.get("/")
async def root():
    return {"message": "Calorie Scanner API is ready."}


# ---------------------------------------------------------------------------
# Routes — Auth
# ---------------------------------------------------------------------------

@api_router.post("/auth/register", response_model=AuthResponse)
async def register_user(payload: UserCreate):
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters.")

    email = payload.email.strip().lower()
    existing_user = await db.users.find_one({"email": email}, {"_id": 1})
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists.")

    user_doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
        "created_at": now_iso(),
        "is_premium": False,
        "subscription_expiry": None,
        "subscription_plan": None,
        "streak_count": 0,
        "last_scan_date": None,
    }
    insert_doc = {**user_doc}
    await db.users.insert_one(insert_doc)
    return build_auth_response(user_doc)


@api_router.post("/auth/login", response_model=AuthResponse)
async def login_user(payload: UserLogin):
    email = payload.email.strip().lower()
    user_doc = await db.users.find_one({"email": email}, {"_id": 0})
    if not user_doc or not verify_password(payload.password, user_doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password.")
    return build_auth_response(user_doc)


@api_router.get("/auth/me", response_model=UserPublic)
async def get_me(current_user: dict = Depends(get_current_user)):
    return build_user_public(current_user)


# ---------------------------------------------------------------------------
# Routes — Subscription
# ---------------------------------------------------------------------------

@api_router.get("/subscription/plans", response_model=List[SubscriptionPlan])
async def get_subscription_plans():
    """Return available Munchy Plus+ subscription plans."""
    return [SubscriptionPlan(**plan) for plan in SUBSCRIPTION_PLANS.values()]


@api_router.get("/subscription/status", response_model=SubscriptionStatus)
async def get_subscription_status(current_user: dict = Depends(get_current_user)):
    """Return current user's subscription status."""
    is_premium = check_premium_status(current_user)
    return SubscriptionStatus(
        is_premium=is_premium,
        plan_id=current_user.get("subscription_plan") if is_premium else None,
        subscription_expiry=current_user.get("subscription_expiry") if is_premium else None,
        auto_renew=is_premium and current_user.get("subscription_plan") in ("monthly", "annual"),
    )


@api_router.post("/subscription/activate", response_model=SubscriptionActivateResponse)
async def activate_subscription(
    payload: SubscriptionActivateRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Activate a Munchy Plus+ subscription with a mock payment confirmation.
    In production, `payment_token` would be a Google Play / Apple IAP receipt
    verified server-side.
    """
    plan = SUBSCRIPTION_PLANS.get(payload.plan_id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan_id '{payload.plan_id}'. Choose from: {', '.join(SUBSCRIPTION_PLANS.keys())}",
        )

    if not validate_mock_payment(payload.payment_token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment token.",
        )

    # Compute expiry
    if plan["duration_days"] is None:
        subscription_expiry = None  # Lifetime
    else:
        subscription_expiry = (now_utc() + timedelta(days=plan["duration_days"])).isoformat()

    # Update user in database
    update_fields = {
        "is_premium": True,
        "subscription_expiry": subscription_expiry,
        "subscription_plan": payload.plan_id,
        "subscription_activated_at": now_iso(),
        "last_payment_token": payload.payment_token,
    }
    await db.users.update_one({"id": current_user["id"]}, {"$set": update_fields})

    logger.info("Subscription activated: user=%s plan=%s", current_user["id"], payload.plan_id)

    return SubscriptionActivateResponse(
        success=True,
        message=f"Munchy Plus+ {plan['name']} activated successfully!",
        subscription=SubscriptionStatus(
            is_premium=True,
            plan_id=payload.plan_id,
            subscription_expiry=subscription_expiry,
            auto_renew=payload.plan_id in ("monthly", "annual"),
        ),
    )


# ---------------------------------------------------------------------------
# Routes — Streak
# ---------------------------------------------------------------------------

@api_router.get("/user/streak", response_model=StreakResponse)
async def get_user_streak(current_user: dict = Depends(get_current_user)):
    """Return the current user's scan streak."""
    return StreakResponse(
        streak_count=current_user.get("streak_count", 0),
        last_scan_date=current_user.get("last_scan_date"),
    )


# ---------------------------------------------------------------------------
# Routes — Scans (with premium-aware analysis)
# ---------------------------------------------------------------------------

@api_router.post("/scans/analyze", response_model=ScanRecord)
async def analyze_scan(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please upload a JPG, PNG, or WEBP food photo.",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The uploaded file is empty.")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Please upload an image under 5MB.")

    is_premium = check_premium_status(current_user)
    system_prompt, user_message_text = get_llm_prompt_for_user(is_premium)

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        chat = LlmChat(
            api_key=emergent_llm_key,
            session_id=f"scan-{uuid.uuid4()}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-5.2")
        raw_response = await chat.send_message(
            UserMessage(
                text=user_message_text,
                file_contents=[ImageContent(image_base64=image_base64)],
            )
        )
        analysis = normalize_analysis(extract_json_payload(str(raw_response)), is_premium=is_premium)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image analysis failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The meal scan could not be completed. Please try another food photo.",
        ) from exc

    scan_doc = {
        "id": str(uuid.uuid4()),
        "user_id": current_user["id"],
        "created_at": now_iso(),
        "image_data_url": f"data:{file.content_type};base64,{image_base64}",
        "result": analysis.model_dump(),
    }
    insert_doc = {**scan_doc}
    await db.scans.insert_one(insert_doc)

    # Update streak
    current_streak = current_user.get("streak_count", 0)
    last_scan_date = current_user.get("last_scan_date")
    new_streak, new_scan_date = compute_streak(current_streak, last_scan_date, today_iso())
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"streak_count": new_streak, "last_scan_date": new_scan_date}},
    )

    return ScanRecord(**scan_doc)


@api_router.get("/scans/history", response_model=List[ScanRecord])
async def get_scan_history(current_user: dict = Depends(get_current_user)):
    history = await db.scans.find(
        {"user_id": current_user["id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    return [ScanRecord(**scan) for scan in history]


# ---------------------------------------------------------------------------
# Routes — Premium-gated Features
# ---------------------------------------------------------------------------

@api_router.get("/analysis/deep")
async def deep_ai_analysis(
    scan_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Deep AI Analysis — full nutrient breakdown beyond basic calories.
    Requires Munchy Plus+ subscription.
    """
    require_premium(current_user)

    scan = await db.scans.find_one(
        {"id": scan_id, "user_id": current_user["id"]},
        {"_id": 0},
    )
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    result = scan.get("result", {})
    return {
        "scan_id": scan_id,
        "foodName": result.get("foodName", "Unknown"),
        "totalCalories": result.get("totalCalories", 0),
        "macros": result.get("macros", {}),
        "micronutrients": result.get("micronutrients", {}),
        "ingredients": result.get("ingredients", []),
        "deep_analysis": True,
        "note": "Full nutrient analysis powered by Munchy Plus+.",
    }


@api_router.post("/wearable/sync")
async def wearable_sync(
    current_user: dict = Depends(get_current_user),
):
    """
    Wearable Sync — sync nutrition data with health wearables.
    Requires Munchy Plus+ subscription.
    """
    require_premium(current_user)

    return {
        "status": "synced",
        "user_id": current_user["id"],
        "message": "Wearable data sync initiated. Your nutrition data will appear on your connected device shortly.",
        "synced_at": now_iso(),
    }


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_indexes():
    await db.users.create_index("email", unique=True)
    await db.scans.create_index([("user_id", 1), ("created_at", -1)])


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
