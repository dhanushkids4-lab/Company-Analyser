import os
import sys
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from company_analyzer.agent import CompanyAgent
from company_analyzer.data_fetcher import CompanyDataFetcher
from company_analyzer.financial_scorer import FinancialScorer
from company_analyzer.llm_analyzer import LLMAnalyzer
from company_analyzer.formatter import ReportFormatter, _fmt_large_num, _fmt_curr, _fmt_pct, _fmt_mult
from company_analyzer.subscription import SubscriptionManager, PLANS

app = FastAPI(title="Company Analyzer Agent Web", version="1.0.0")

@app.get("/healthz")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "app": "Company Analyzer Agent"}

# Agent and Subscription Manager instances
agent = CompanyAgent()
db_path = os.path.join(os.path.dirname(__file__), "..", "subscriptions.db")
sub_manager = SubscriptionManager(db_path=db_path)

# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


class ChatRequest(BaseModel):
    symbol: str
    question: str
    user_id: Optional[str] = "default_user"
    company_data: Optional[dict] = None
    score_data: Optional[dict] = None


class CheckoutRequest(BaseModel):
    plan_id: str
    user_id: Optional[str] = "default_user"
    success_url: Optional[str] = "http://127.0.0.1:8000"
    cancel_url: Optional[str] = "http://127.0.0.1:8000"


class DemoUpgradeRequest(BaseModel):
    plan_id: str
    user_id: Optional[str] = "default_user"


class RazorpayOrderRequest(BaseModel):
    plan_id: str
    user_id: Optional[str] = "default_user"
    currency: Optional[str] = "INR"


class RazorpayVerifyRequest(BaseModel):
    user_id: Optional[str] = "default_user"
    plan_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# --- Subscription & Payment Endpoints ---

@app.get("/api/subscription/plans")
async def get_plans():
    """Returns available subscription tiers and features."""
    return {
        "plans": PLANS,
        "razorpay_key_id": sub_manager.razorpay_key_id or "rzp_test_mock_key"
    }


@app.get("/api/subscription/status")
async def get_subscription_status(user_id: str = "default_user"):
    """Returns the user's current subscription tier and remaining daily quota."""
    quota = sub_manager.check_quota(user_id)
    return quota


# --- Razorpay Integration Endpoints ---

@app.post("/api/razorpay/create-order")
async def razorpay_create_order(req: RazorpayOrderRequest):
    """Creates a Razorpay order for UPI / Card / NetBanking payment."""
    try:
        order = sub_manager.create_razorpay_order(
            user_id=req.user_id or "default_user",
            plan_id=req.plan_id,
            currency=req.currency or "INR"
        )
        return order
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/razorpay/verify-payment")
async def razorpay_verify_payment(req: RazorpayVerifyRequest):
    """Verifies Razorpay payment signature and activates user plan."""
    try:
        result = sub_manager.verify_razorpay_payment(
            user_id=req.user_id or "default_user",
            plan_id=req.plan_id,
            razorpay_order_id=req.razorpay_order_id,
            razorpay_payment_id=req.razorpay_payment_id,
            razorpay_signature=req.razorpay_signature
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/subscription/checkout")
async def create_checkout(req: CheckoutRequest):
    """Creates a Stripe Checkout session or sandbox activation."""
    try:
        res = sub_manager.create_checkout_session(
            user_id=req.user_id,
            plan_id=req.plan_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/subscription/demo-upgrade")
async def demo_upgrade(req: DemoUpgradeRequest):
    """Instantly switches plan tier for testing and demo purposes."""
    try:
        sub_manager.set_user_plan(req.user_id, req.plan_id)
        quota = sub_manager.check_quota(req.user_id)
        return {
            "status": "success",
            "message": f"Switched to {PLANS[req.plan_id]['name']}",
            "quota": quota
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/subscription/webhook")
async def stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    """Receives and processes Stripe subscription events."""
    try:
        payload = await request.body()
        result = sub_manager.handle_webhook(payload, stripe_signature or "")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- Core Analysis & Agent Endpoints ---

@app.get("/api/search")
async def search_company(q: str = Query(..., min_length=1)):
    """Search for matching company tickers and names."""
    try:
        resolved = CompanyDataFetcher.resolve_ticker(q)
        return {"result": resolved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analyze")
async def analyze_company(
    query: str = Query(..., min_length=1),
    user_id: str = "default_user",
    use_llm: bool = True
):
    """Fetches fundamentals, checks subscription quota, and returns full company stats."""
    quota = sub_manager.check_quota(user_id)
    if not quota["allowed"] or (quota.get("daily_limit") != -1 and (quota.get("remaining") is not None and quota.get("remaining") <= 0)):
        raise HTTPException(
            status_code=429,
            detail=f"Daily free limit reached ({quota['daily_limit']}/{quota['daily_limit']} analyses used today). Please upgrade to Pro for unlimited analyses."
        )

    try:
        result = agent.analyze(
            query,
            use_llm=use_llm,
            display=False
        )
        
        # Record usage
        sub_manager.record_usage(user_id)
        updated_quota = sub_manager.check_quota(user_id)
        result["quota"] = updated_quota
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/chat")
async def chat_with_agent(req: ChatRequest):
    """Answers specific user questions about the analyzed company (Pro & Enterprise feature)."""
    user_id = req.user_id or "default_user"
    quota = sub_manager.check_quota(user_id)

    # Check plan permissions
    if not quota["features"].get("has_chat", False) and quota["plan"] == "free":
        raise HTTPException(
            status_code=403,
            detail="The Interactive AI Agent Chat assistant is a Pro Analyst feature. Please upgrade to unlock unlimited Q&A."
        )

    try:
        data = req.company_data
        score = req.score_data
        
        # If not provided in body, fetch fresh
        if not data or not score:
            res = agent.analyze(req.symbol, use_llm=False, display=False)
            data = res["company_data"]
            score = res["scoring"]

        profile = data.get("profile", {})
        val = data.get("valuation", {})
        prof = data.get("profitability", {})
        bs = data.get("balance_sheet", {})
        price = data.get("price_stats", {})
        targets = data.get("analyst_targets", {})

        # Context prompt
        context = (
            f"Company: {profile.get('name')} ({profile.get('symbol')})\n"
            f"Sector: {profile.get('sector')} | Industry: {profile.get('industry')}\n"
            f"Price: {price.get('current_price')} {price.get('currency')} (52W: {price.get('fifty_two_week_low')} - {price.get('fifty_two_week_high')})\n"
            f"Market Cap: {price.get('market_cap')}\n"
            f"Valuation: Trailing P/E {val.get('trailing_pe')}, Forward P/E {val.get('forward_pe')}, PEG {val.get('peg_ratio')}, P/S {val.get('price_to_sales')}, EV/EBITDA {val.get('ev_to_ebitda')}\n"
            f"Margins: Gross {prof.get('gross_margin')}, Operating {prof.get('operating_margin')}, Net {prof.get('profit_margin')}, ROE {prof.get('return_on_equity')}\n"
            f"Balance Sheet: Cash {bs.get('total_cash')}, Debt {bs.get('total_debt')}, Current Ratio {bs.get('current_ratio')}, Debt/Equity {bs.get('debt_to_equity')}\n"
            f"Analyst Consensus: {targets.get('recommendation_key')} (Target Mean: {targets.get('target_mean_price')})\n"
            f"Health Score: {score.get('overall_score')}/100 (Grade: {score.get('grade')})\n"
            f"Strengths: {', '.join(score.get('strengths', []))}\n"
            f"Risks: {', '.join(score.get('risks', []))}"
        )

        llm = agent.llm
        if llm.is_available:
            import requests
            headers = {"Authorization": f"Bearer {llm.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": llm.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert Wall Street financial analyst agent. Answer the user's question directly, accurately, and quantitatively based strictly on the provided financial metrics. Keep responses concise, objective, and insightful."
                    },
                    {
                        "role": "user",
                        "content": f"Company Data:\n{context}\n\nUser Question: {req.question}"
                    }
                ],
                "temperature": 0.2
            }
            endpoint = f"{llm.base_url.rstrip('/')}/chat/completions"
            res = requests.post(endpoint, headers=headers, json=payload, timeout=25)
            if res.status_code == 200:
                answer = res.json()["choices"][0]["message"]["content"].strip()
                return {"answer": answer}

        # Fallback intelligent answer synthesizer
        q_lower = req.question.lower()
        if "debt" in q_lower or "solvency" in q_lower or "cash" in q_lower:
            ans = f"**Balance Sheet & Debt Assessment for {profile.get('name')}:**\n\n"
            curr = "$" if profile.get("currency") == "USD" else f"{profile.get('currency', '')} "
            ans += f"- **Total Cash:** {_fmt_large_num(bs.get('total_cash'), curr)}\n"
            ans += f"- **Total Debt:** {_fmt_large_num(bs.get('total_debt'), curr)}\n"
            ans += f"- **Debt to Equity:** {bs.get('debt_to_equity', 'N/A')}%\n"
            ans += f"- **Current Ratio:** {bs.get('current_ratio', 'N/A')}\n\n"
            if bs.get("net_debt", 0) and bs.get("net_debt", 0) < 0:
                ans += "The company is in a **net cash** position (cash reserves exceed total debt obligations), indicating minimal insolvency risk."
            else:
                ans += "The company maintains active debt leverage. Monitor debt maturities and interest coverage against operating income."
            return {"answer": ans}

        elif "valuation" in q_lower or "pe" in q_lower or "expensive" in q_lower or "cheap" in q_lower:
            ans = f"**Valuation Breakdown for {profile.get('name')} ({profile.get('symbol')}):**\n\n"
            ans += f"- **Trailing P/E:** {val.get('trailing_pe', 'N/A')}\n"
            ans += f"- **Forward P/E:** {val.get('forward_pe', 'N/A')}\n"
            ans += f"- **PEG Ratio:** {val.get('peg_ratio', 'N/A')}\n"
            ans += f"- **Price / Sales:** {val.get('price_to_sales', 'N/A')}x\n"
            ans += f"- **EV / EBITDA:** {val.get('ev_to_ebitda', 'N/A')}x\n\n"
            ans += f"**Verdict:** {score.get('bear_thesis') if (val.get('trailing_pe') or 0) > 30 else score.get('bull_thesis')}"
            return {"answer": ans}

        elif "margin" in q_lower or "profit" in q_lower or "roe" in q_lower:
            ans = f"**Profitability & Efficiency for {profile.get('name')}:**\n\n"
            ans += f"- **Gross Margin:** {prof.get('gross_margin', 0)*100:.2f}%\n"
            ans += f"- **Operating Margin:** {prof.get('operating_margin', 0)*100:.2f}%\n"
            ans += f"- **Net Profit Margin:** {prof.get('profit_margin', 0)*100:.2f}%\n"
            ans += f"- **Return on Equity (ROE):** {prof.get('return_on_equity', 0)*100:.2f}%\n\n"
            ans += f"{score.get('bull_thesis')}"
            return {"answer": ans}

        else:
            ans = f"**Analysis Summary for {profile.get('name')} ({profile.get('symbol')}):**\n\n"
            ans += f"- **Health Score:** {score.get('overall_score')}/100 (Grade {score.get('grade')})\n"
            ans += f"- **Consensus:** {targets.get('recommendation_key', 'N/A').upper()} with mean target {price.get('currency', '$')}{targets.get('target_mean_price', 'N/A')}\n"
            ans += f"- **Bull Thesis:** {score.get('bull_thesis')}\n"
            ans += f"- **Bear Thesis:** {score.get('bear_thesis')}\n"
            return {"answer": ans}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def get_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Company Analyzer Web UI Loading...</h1>")

# Mount static directory for CSS/JS assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
