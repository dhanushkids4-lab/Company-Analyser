import os
import hmac
import hashlib
import sqlite3
import datetime
from typing import Dict, Any, Optional
import razorpay
import stripe

# Plan definitions with both INR and USD pricing
PLANS = {
    "free": {
        "id": "free",
        "name": "Free Tier",
        "price_usd": 0,
        "price_inr": 0,
        "daily_analysis_limit": 3,
        "features": [
            "3 Company analyses per day",
            "Core financial & valuation multiples",
            "Solvency & health score (0-100)",
            "Basic Wall Street consensus"
        ],
        "has_chat": False,
        "has_charts": False,
        "has_memo": False,
        "has_export": False
    },
    "pro": {
        "id": "pro",
        "name": "Pro Analyst",
        "price_usd": 19,
        "price_inr": 1499,
        "daily_analysis_limit": -1,  # Unlimited
        "features": [
            "Unlimited company analyses",
            "Multi-year interactive financial charts",
            "Full AI Strategic Investment Memo",
            "Interactive Agent Q&A Chat assistant",
            "One-click HTML, JSON & Markdown exports",
            "Global multi-exchange coverage"
        ],
        "has_chat": True,
        "has_charts": True,
        "has_memo": True,
        "has_export": True
    },
    "enterprise": {
        "id": "enterprise",
        "name": "Institutional",
        "price_usd": 49,
        "price_inr": 3999,
        "daily_analysis_limit": -1,  # Unlimited
        "features": [
            "Everything in Pro Analyst",
            "Priority LLM inference & speed",
            "API programmatic access key",
            "Peer benchmarking & custom scoring",
            "Dedicated support & custom reporting"
        ],
        "has_chat": True,
        "has_charts": True,
        "has_memo": True,
        "has_export": True
    }
}


class SubscriptionManager:
    """Manages user subscription tiers, usage quotas, Stripe & Razorpay billing."""

    def __init__(self, db_path: str = "subscriptions.db"):
        self.db_path = db_path
        
        # Razorpay config
        self.razorpay_key_id = os.getenv("RAZORPAY_KEY_ID")
        self.razorpay_key_secret = os.getenv("RAZORPAY_KEY_SECRET")
        self.razorpay_client = None
        if self.razorpay_key_id and self.razorpay_key_secret:
            self.razorpay_client = razorpay.Client(auth=(self.razorpay_key_id, self.razorpay_key_secret))

        # Stripe config
        self.stripe_secret_key = os.getenv("STRIPE_SECRET_KEY")
        self.stripe_publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

        if self.stripe_secret_key:
            stripe.api_key = self.stripe_secret_key

        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT,
                    plan TEXT DEFAULT 'free',
                    status TEXT DEFAULT 'active',
                    stripe_customer_id TEXT,
                    stripe_subscription_id TEXT,
                    razorpay_payment_id TEXT,
                    current_period_end TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usage (
                    user_id TEXT,
                    date TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    gateway TEXT,
                    payment_id TEXT,
                    order_id TEXT,
                    plan_id TEXT,
                    amount REAL,
                    currency TEXT,
                    status TEXT,
                    created_at TEXT
                )
            """)
            # --- Migration: add Razorpay column to pre-existing users table ---
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            if "razorpay_payment_id" not in columns:
                cursor.execute("ALTER TABLE users ADD COLUMN razorpay_payment_id TEXT")
            conn.commit()

    def get_or_create_user(self, user_id: str = "default_user", email: Optional[str] = None) -> Dict[str, Any]:
        now_str = datetime.datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Create default free user
            cursor.execute(
                "INSERT INTO users (user_id, email, plan, status, created_at) VALUES (?, ?, 'free', 'active', ?)",
                (user_id, email or f"{user_id}@example.com", now_str)
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            return dict(cursor.fetchone())

    def get_usage(self, user_id: str) -> int:
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count FROM usage WHERE user_id = ? AND date = ?", (user_id, today))
            row = cursor.fetchone()
            return row[0] if row else 0

    def record_usage(self, user_id: str):
        today = datetime.date.today().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usage (user_id, date, count) VALUES (?, ?, 1)
                ON CONFLICT(user_id, date) DO UPDATE SET count = count + 1
            """, (user_id, today))
            conn.commit()

    def check_quota(self, user_id: str) -> Dict[str, Any]:
        user = self.get_or_create_user(user_id)
        plan_id = user.get("plan", "free")
        plan_info = PLANS.get(plan_id, PLANS["free"])
        usage_count = self.get_usage(user_id)
        daily_limit = plan_info["daily_analysis_limit"]

        allowed = True
        remaining = None
        if daily_limit != -1:
            remaining = max(0, daily_limit - usage_count)
            if usage_count >= daily_limit:
                allowed = False

        return {
            "allowed": allowed,
            "plan": plan_id,
            "plan_name": plan_info["name"],
            "usage_today": usage_count,
            "daily_limit": daily_limit,
            "remaining": remaining,
            "remaining_today": remaining,
            "features": plan_info
        }

    def set_user_plan(self, user_id: str, plan_id: str, rzp_payment_id: Optional[str] = None):
        if plan_id not in PLANS:
            raise ValueError(f"Invalid plan: {plan_id}")

        period_end = (datetime.datetime.utcnow() + datetime.timedelta(days=30)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET plan = ?, status = 'active', razorpay_payment_id = COALESCE(?, razorpay_payment_id),
                    current_period_end = ?
                WHERE user_id = ?
            """, (plan_id, rzp_payment_id, period_end, user_id))
            conn.commit()

    # --- Razorpay Order & Payment Verification ---

    def create_razorpay_order(self, user_id: str, plan_id: str, currency: str = "INR") -> Dict[str, Any]:
        """Creates a Razorpay order for UPI / Card / NetBanking payment."""
        if plan_id not in ("pro", "enterprise"):
            raise ValueError("Can only purchase paid plans (pro, enterprise)")

        plan_info = PLANS[plan_id]
        is_inr = currency.upper() == "INR"
        amount_val = plan_info["price_inr"] if is_inr else plan_info["price_usd"]
        amount_subunits = int(amount_val * 100)  # In paise or cents

        # If live/test Razorpay API credentials are configured
        if self.razorpay_client:
            try:
                order_data = {
                    "amount": amount_subunits,
                    "currency": currency.upper(),
                    "receipt": f"rcpt_{user_id[:8]}_{int(datetime.datetime.utcnow().timestamp())}",
                    "notes": {
                        "user_id": user_id,
                        "plan_id": plan_id,
                        "plan_name": plan_info["name"]
                    }
                }
                order = self.razorpay_client.order.create(data=order_data)
                return {
                    "mode": "razorpay",
                    "order_id": order["id"],
                    "key_id": self.razorpay_key_id,
                    "amount": amount_subunits,
                    "currency": currency.upper(),
                    "plan_name": plan_info["name"],
                    "plan_id": plan_id
                }
            except Exception as e:
                pass

        # Sandbox / Mock Order Fallback when API keys are not provided
        mock_order_id = f"order_mock_{int(datetime.datetime.utcnow().timestamp())}"
        return {
            "mode": "sandbox",
            "order_id": mock_order_id,
            "key_id": self.razorpay_key_id or "rzp_test_mock_key",
            "amount": amount_subunits,
            "currency": currency.upper(),
            "plan_name": plan_info["name"],
            "plan_id": plan_id,
            "message": "Running in Razorpay Sandbox / Demo mode."
        }

    def verify_razorpay_payment(
        self,
        user_id: str,
        plan_id: str,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str
    ) -> Dict[str, Any]:
        """Verifies Razorpay payment signature and activates the subscription."""
        now_str = datetime.datetime.utcnow().isoformat()
        
        # Verify signature if secret key is present
        if self.razorpay_key_secret and not razorpay_order_id.startswith("order_mock_"):
            try:
                msg = f"{razorpay_order_id}|{razorpay_payment_id}"
                expected_sig = hmac.new(
                    self.razorpay_key_secret.encode("utf-8"),
                    msg.encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(expected_sig, razorpay_signature):
                    raise ValueError("Invalid Razorpay payment signature verification failed.")
            except Exception as e:
                raise ValueError(f"Razorpay verification failed: {str(e)}")

        # Upgrade User Plan in DB
        self.set_user_plan(user_id=user_id, plan_id=plan_id, rzp_payment_id=razorpay_payment_id)

        # Log payment record
        plan_info = PLANS.get(plan_id, PLANS["pro"])
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO payments (user_id, gateway, payment_id, order_id, plan_id, amount, currency, status, created_at)
                VALUES (?, 'razorpay', ?, ?, ?, ?, 'INR', 'captured', ?)
            """, (user_id, razorpay_payment_id, razorpay_order_id, plan_id, plan_info.get("price_inr", 1499), now_str))
            conn.commit()

        updated_quota = self.check_quota(user_id)
        return {
            "status": "success",
            "message": f"Payment verified! Upgraded to {plan_info['name']}.",
            "plan": plan_id,
            "quota": updated_quota
        }
