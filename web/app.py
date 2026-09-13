import os
import sys
import json
import html
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


# Ensure parent directory is in sys.path
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
)


from company_analyzer.agent import CompanyAgent
from company_analyzer.data_fetcher import CompanyDataFetcher
from company_analyzer.financial_scorer import FinancialScorer
from company_analyzer.llm_analyzer import LLMAnalyzer
from company_analyzer.formatter import (
    ReportFormatter,
    _fmt_large_num,
    _fmt_curr,
    _fmt_pct,
    _fmt_mult,
)
from company_analyzer.subscription import SubscriptionManager, PLANS


app = FastAPI(
    title="Company Analyzer Agent Web",
    version="1.0.0"
)


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/healthz")
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "app": "Company Analyzer Agent"
    }


# --------------------------------------------------
# AGENT AND SUBSCRIPTION MANAGER
# --------------------------------------------------

agent = CompanyAgent()

db_path = os.path.join(
    os.path.dirname(__file__),
    "..",
    "subscriptions.db"
)

sub_manager = SubscriptionManager(
    db_path=db_path
)


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------

STATIC_DIR = os.path.join(
    os.path.dirname(__file__),
    "static"
)

os.makedirs(
    STATIC_DIR,
    exist_ok=True
)


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

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


# --------------------------------------------------
# SUBSCRIPTION & PAYMENT ENDPOINTS
# --------------------------------------------------

@app.get("/api/subscription/plans")
async def get_plans():
    """Returns available subscription tiers and features."""

    return {
        "plans": PLANS,
        "razorpay_key_id": (
            sub_manager.razorpay_key_id
            or "rzp_test_mock_key"
        )
    }


@app.get("/api/subscription/status")
async def get_subscription_status(
    user_id: str = "default_user"
):
    """Returns the user's subscription tier and daily quota."""

    quota = sub_manager.check_quota(
        user_id
    )

    return quota


# --------------------------------------------------
# RAZORPAY ENDPOINTS
# --------------------------------------------------

@app.post("/api/razorpay/create-order")
async def razorpay_create_order(
    req: RazorpayOrderRequest
):
    """Creates a Razorpay order."""

    try:

        order = sub_manager.create_razorpay_order(
            user_id=req.user_id or "default_user",
            plan_id=req.plan_id,
            currency=req.currency or "INR"
        )

        return order

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post("/api/razorpay/verify-payment")
async def razorpay_verify_payment(
    req: RazorpayVerifyRequest
):
    """Verifies Razorpay payment signature."""

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

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# --------------------------------------------------
# STRIPE / SUBSCRIPTION ENDPOINTS
# --------------------------------------------------

@app.post("/api/subscription/checkout")
async def create_checkout(
    req: CheckoutRequest
):
    """Creates a Stripe checkout session."""

    try:

        res = sub_manager.create_checkout_session(
            user_id=req.user_id,
            plan_id=req.plan_id,
            success_url=req.success_url,
            cancel_url=req.cancel_url
        )

        return res

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post("/api/subscription/demo-upgrade")
async def demo_upgrade(
    req: DemoUpgradeRequest
):
    """Switches subscription tier for testing."""

    try:

        sub_manager.set_user_plan(
            req.user_id,
            req.plan_id
        )

        quota = sub_manager.check_quota(
            req.user_id
        )

        return {
            "status": "success",
            "message": (
                f"Switched to "
                f"{PLANS[req.plan_id]['name']}"
            ),
            "quota": quota
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


@app.post("/api/subscription/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None)
):
    """Receives Stripe subscription events."""

    try:

        payload = await request.body()

        result = sub_manager.handle_webhook(
            payload,
            stripe_signature or ""
        )

        return result

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )


# --------------------------------------------------
# COMPANY SEARCH
# --------------------------------------------------

@app.get("/api/search")
async def search_company(
    q: str = Query(..., min_length=1)
):
    """Search for matching company tickers."""

    try:

        resolved = CompanyDataFetcher.resolve_ticker(
            q
        )

        return {
            "result": resolved
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# --------------------------------------------------
# COMPANY ANALYSIS
# --------------------------------------------------

@app.get("/api/analyze")
async def analyze_company(
    query: str = Query(..., min_length=1),
    user_id: str = "default_user",
    use_llm: bool = True
):
    """Fetches and analyzes company financial data."""

    quota = sub_manager.check_quota(
        user_id
    )

    if (
        not quota["allowed"]
        or (
            quota.get("daily_limit") != -1
            and quota.get("remaining") is not None
            and quota.get("remaining") <= 0
        )
    ):

        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily free limit reached "
                f"({quota['daily_limit']}/"
                f"{quota['daily_limit']} analyses used today). "
                f"Please upgrade to Pro for unlimited analyses."
            )
        )

    try:

        result = agent.analyze(
            query,
            use_llm=use_llm,
            display=False
        )

        # Record usage only after successful analysis
        sub_manager.record_usage(
            user_id
        )

        updated_quota = sub_manager.check_quota(
            user_id
        )

        result["quota"] = updated_quota

        return result

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Analysis failed: {str(e)}"
            )
        )


# --------------------------------------------------
# EXPORT ANALYSIS
# --------------------------------------------------

@app.get("/api/export")
async def export_analysis(
    symbol: str = Query(..., min_length=1),
    format: str = Query("json")
):
    """
    Export company analysis as HTML or JSON.

    Examples:
    /api/export?symbol=NVDA&format=html
    /api/export?symbol=NVDA&format=json
    """

    try:

        # Fetch fresh analysis data
        result = agent.analyze(
            symbol,
            use_llm=False,
            display=False
        )

        # Convert data into JSON-safe format
        safe_result = jsonable_encoder(
            result
        )

        export_format = format.lower().strip()

        # ------------------------------
        # JSON EXPORT
        # ------------------------------

        if export_format == "json":

            content = json.dumps(
                safe_result,
                indent=2,
                default=str
            )

            return Response(
                content=content,
                media_type="application/json",
                headers={
                    "Content-Disposition": (
                        f'attachment; '
                        f'filename="{symbol}_analysis.json"'
                    )
                }
            )

        # ------------------------------
        # HTML EXPORT
        # ------------------------------

        if export_format == "html":

            company_data = safe_result.get(
                "company_data",
                {}
            )

            scoring = safe_result.get(
                "scoring",
                {}
            )

            profile = company_data.get(
                "profile",
                {}
            )

            valuation = company_data.get(
                "valuation",
                {}
            )

            profitability = company_data.get(
                "profitability",
                {}
            )

            balance_sheet = company_data.get(
                "balance_sheet",
                {}
            )

            price_stats = company_data.get(
                "price_stats",
                {}
            )

            company_name = html.escape(
                str(
                    profile.get(
                        "name",
                        symbol
                    )
                )
            )

            safe_symbol = html.escape(
                str(symbol)
            )

            score = scoring.get(
                "overall_score",
                "N/A"
            )

            grade = scoring.get(
                "grade",
                "N/A"
            )

            strengths = scoring.get(
                "strengths",
                []
            )

            risks = scoring.get(
                "risks",
                []
            )

            strengths_html = ""

            if strengths:
                for item in strengths:
                    strengths_html += (
                        f"<li>{html.escape(str(item))}</li>"
                    )
            else:
                strengths_html = (
                    "<li>No strengths available</li>"
                )

            risks_html = ""

            if risks:
                for item in risks:
                    risks_html += (
                        f"<li>{html.escape(str(item))}</li>"
                    )
            else:
                risks_html = (
                    "<li>No risks available</li>"
                )

            page = f"""
<!DOCTYPE html>
<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    {company_name} Financial Analysis
</title>

<style>

body {{
    font-family:
        Arial,
        Helvetica,
        sans-serif;

    background: #0b1120;
    color: #e5e7eb;

    margin: 0;
    padding: 40px;
}}

.container {{
    max-width: 1200px;
    margin: auto;
}}

h1 {{
    color: #38bdf8;
    margin-bottom: 5px;
}}

.subtitle {{
    color: #94a3b8;
    margin-bottom: 30px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(
            auto-fit,
            minmax(300px, 1fr)
        );

    gap: 20px;
}}

.card {{
    background: #111827;
    border: 1px solid #334155;
    border-radius: 12px;

    padding: 25px;
}}

.card h2 {{
    margin-top: 0;
    color: #67e8f9;
}}

.score {{
    font-size: 48px;
    font-weight: bold;
    color: #34d399;
}}

.grade {{
    font-size: 28px;
    color: #fbbf24;
}}

.metric {{
    display: flex;
    justify-content: space-between;

    padding: 10px 0;

    border-bottom:
        1px solid #1e293b;
}}

.metric:last-child {{
    border-bottom: none;
}}

.label {{
    color: #94a3b8;
}}

.value {{
    font-weight: bold;
}}

.strengths li {{
    color: #6ee7b7;
    margin-bottom: 10px;
}}

.risks li {{
    color: #fda4af;
    margin-bottom: 10px;
}}

.footer {{
    margin-top: 40px;
    color: #64748b;
    text-align: center;
}}

</style>

</head>

<body>

<div class="container">

<h1>
    {company_name}
</h1>

<div class="subtitle">
    {safe_symbol} · Company Financial Analysis
</div>


<div class="grid">

<div class="card">

<h2>
    Health Score
</h2>

<div class="score">
    {html.escape(str(score))}
</div>

<div class="grade">
    Grade: {html.escape(str(grade))}
</div>

</div>


<div class="card">

<h2>
    Price Information
</h2>

<div class="metric">
    <span class="label">
        Current Price
    </span>

    <span class="value">
        {html.escape(str(price_stats.get('current_price', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Market Cap
    </span>

    <span class="value">
        {html.escape(str(price_stats.get('market_cap', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        52 Week High
    </span>

    <span class="value">
        {html.escape(str(price_stats.get('fifty_two_week_high', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        52 Week Low
    </span>

    <span class="value">
        {html.escape(str(price_stats.get('fifty_two_week_low', 'N/A')))}
    </span>
</div>

</div>


<div class="card">

<h2>
    Valuation
</h2>

<div class="metric">
    <span class="label">
        Trailing P/E
    </span>

    <span class="value">
        {html.escape(str(valuation.get('trailing_pe', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Forward P/E
    </span>

    <span class="value">
        {html.escape(str(valuation.get('forward_pe', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        PEG Ratio
    </span>

    <span class="value">
        {html.escape(str(valuation.get('peg_ratio', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Price / Sales
    </span>

    <span class="value">
        {html.escape(str(valuation.get('price_to_sales', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        EV / EBITDA
    </span>

    <span class="value">
        {html.escape(str(valuation.get('ev_to_ebitda', 'N/A')))}
    </span>
</div>

</div>


<div class="card">

<h2>
    Profitability
</h2>

<div class="metric">
    <span class="label">
        Revenue
    </span>

    <span class="value">
        {html.escape(str(profitability.get('revenue', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Gross Margin
    </span>

    <span class="value">
        {html.escape(str(profitability.get('gross_margin', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Operating Margin
    </span>

    <span class="value">
        {html.escape(str(profitability.get('operating_margin', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Net Profit Margin
    </span>

    <span class="value">
        {html.escape(str(profitability.get('profit_margin', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Return on Equity
    </span>

    <span class="value">
        {html.escape(str(profitability.get('return_on_equity', 'N/A')))}
    </span>
</div>

</div>


<div class="card">

<h2>
    Balance Sheet
</h2>

<div class="metric">
    <span class="label">
        Total Cash
    </span>

    <span class="value">
        {html.escape(str(balance_sheet.get('total_cash', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Total Debt
    </span>

    <span class="value">
        {html.escape(str(balance_sheet.get('total_debt', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Net Debt
    </span>

    <span class="value">
        {html.escape(str(balance_sheet.get('net_debt', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Debt to Equity
    </span>

    <span class="value">
        {html.escape(str(balance_sheet.get('debt_to_equity', 'N/A')))}
    </span>
</div>

<div class="metric">
    <span class="label">
        Current Ratio
    </span>

    <span class="value">
        {html.escape(str(balance_sheet.get('current_ratio', 'N/A')))}
    </span>
</div>

</div>


<div class="card strengths">

<h2>
    Key Strengths
</h2>

<ul>
    {strengths_html}
</ul>

</div>


<div class="card risks">

<h2>
    Key Risks & Watchpoints
</h2>

<ul>
    {risks_html}
</ul>

</div>

</div>


<div class="footer">

Generated by Company Analyzer Agent

</div>

</div>

</body>

</html>
"""

            return Response(
                content=page,
                media_type="text/html",
                headers={
                    "Content-Disposition": (
                        f'attachment; '
                        f'filename="{symbol}_analysis.html"'
                    )
                }
            )

        # Invalid format
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported export format. "
                "Use html or json."
            )
        )

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Export failed: {str(e)}"
            )
        )


# --------------------------------------------------
# CHAT WITH AGENT
# --------------------------------------------------

@app.post("/api/chat")
async def chat_with_agent(
    req: ChatRequest
):
    """Answers questions about the analyzed company."""

    user_id = (
        req.user_id
        or "default_user"
    )

    quota = sub_manager.check_quota(
        user_id
    )

    # Check plan permissions
    if (
        not quota["features"].get(
            "has_chat",
            False
        )
        and quota["plan"] == "free"
    ):

        raise HTTPException(
            status_code=403,
            detail=(
                "The Interactive AI Agent Chat assistant "
                "is a Pro Analyst feature. "
                "Please upgrade to unlock unlimited Q&A."
            )
        )

    try:

        data = req.company_data
        score = req.score_data

        # Fetch fresh data if necessary
        if not data or not score:

            res = agent.analyze(
                req.symbol,
                use_llm=False,
                display=False
            )

            data = res["company_data"]
            score = res["scoring"]

        profile = data.get(
            "profile",
            {}
        )

        val = data.get(
            "valuation",
            {}
        )

        prof = data.get(
            "profitability",
            {}
        )

        bs = data.get(
            "balance_sheet",
            {}
        )

        price = data.get(
            "price_stats",
            {}
        )

        targets = data.get(
            "analyst_targets",
            {}
        )


        # Build AI context
        context = (

            f"Company: "
            f"{profile.get('name')} "
            f"({profile.get('symbol')})\n"

            f"Sector: "
            f"{profile.get('sector')} | "
            f"Industry: "
            f"{profile.get('industry')}\n"

            f"Price: "
            f"{price.get('current_price')} "
            f"{price.get('currency')} "
            f"(52W: "
            f"{price.get('fifty_two_week_low')} - "
            f"{price.get('fifty_two_week_high')})\n"

            f"Market Cap: "
            f"{price.get('market_cap')}\n"

            f"Valuation: "
            f"Trailing P/E {val.get('trailing_pe')}, "
            f"Forward P/E {val.get('forward_pe')}, "
            f"PEG {val.get('peg_ratio')}, "
            f"P/S {val.get('price_to_sales')}, "
            f"EV/EBITDA {val.get('ev_to_ebitda')}\n"

            f"Margins: "
            f"Gross {prof.get('gross_margin')}, "
            f"Operating {prof.get('operating_margin')}, "
            f"Net {prof.get('profit_margin')}, "
            f"ROE {prof.get('return_on_equity')}\n"

            f"Balance Sheet: "
            f"Cash {bs.get('total_cash')}, "
            f"Debt {bs.get('total_debt')}, "
            f"Current Ratio {bs.get('current_ratio')}, "
            f"Debt/Equity {bs.get('debt_to_equity')}\n"

            f"Analyst Consensus: "
            f"{targets.get('recommendation_key')} "
            f"(Target Mean: "
            f"{targets.get('target_mean_price')})\n"

            f"Health Score: "
            f"{score.get('overall_score')}/100 "
            f"(Grade: "
            f"{score.get('grade')})\n"

            f"Strengths: "
            f"{', '.join(score.get('strengths', []))}\n"

            f"Risks: "
            f"{', '.join(score.get('risks', []))}"
        )


        # --------------------------------------------------
        # LLM RESPONSE
        # --------------------------------------------------

        llm = agent.llm

        if llm.is_available:

            import requests

            headers = {
                "Authorization":
                    f"Bearer {llm.api_key}",

                "Content-Type":
                    "application/json"
            }

            payload = {
                "model": llm.model,

                "messages": [

                    {
                        "role": "system",

                        "content": (
                            "You are an expert Wall Street "
                            "financial analyst agent. "
                            "Answer the user's question directly, "
                            "accurately, and quantitatively based "
                            "strictly on the provided financial metrics. "
                            "Keep responses concise, objective, "
                            "and insightful."
                        )
                    },

                    {
                        "role": "user",

                        "content": (
                            f"Company Data:\n"
                            f"{context}\n\n"
                            f"User Question: "
                            f"{req.question}"
                        )
                    }

                ],

                "temperature": 0.2
            }

            endpoint = (
                f"{llm.base_url.rstrip('/')}"
                f"/chat/completions"
            )

            res = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=25
            )

            if res.status_code == 200:

                answer = (
                    res.json()
                    ["choices"][0]
                    ["message"]
                    ["content"]
                    .strip()
                )

                return {
                    "answer": answer
                }


        # --------------------------------------------------
        # FALLBACK ANSWERS
        # --------------------------------------------------

        q_lower = (
            req.question.lower()
        )


        # DEBT
        if (
            "debt" in q_lower
            or "solvency" in q_lower
            or "cash" in q_lower
        ):

            ans = (
                f"**Balance Sheet & Debt Assessment "
                f"for {profile.get('name')}:**\n\n"
            )

            curr = (
                "$"
                if profile.get("currency") == "USD"
                else f"{profile.get('currency', '')} "
            )

            ans += (
                f"- **Total Cash:** "
                f"{_fmt_large_num(bs.get('total_cash'), curr)}\n"
            )

            ans += (
                f"- **Total Debt:** "
                f"{_fmt_large_num(bs.get('total_debt'), curr)}\n"
            )

            ans += (
                f"- **Debt to Equity:** "
                f"{bs.get('debt_to_equity', 'N/A')}%\n"
            )

            ans += (
                f"- **Current Ratio:** "
                f"{bs.get('current_ratio', 'N/A')}\n\n"
            )

            if (
                bs.get("net_debt", 0)
                and bs.get("net_debt", 0) < 0
            ):

                ans += (
                    "The company is in a **net cash** position "
                    "(cash reserves exceed total debt obligations), "
                    "indicating minimal insolvency risk."
                )

            else:

                ans += (
                    "The company maintains active debt leverage. "
                    "Monitor debt maturities and interest coverage "
                    "against operating income."
                )

            return {
                "answer": ans
            }


        # VALUATION
        elif (
            "valuation" in q_lower
            or "pe" in q_lower
            or "expensive" in q_lower
            or "cheap" in q_lower
        ):

            ans = (
                f"**Valuation Breakdown for "
                f"{profile.get('name')} "
                f"({profile.get('symbol')}):**\n\n"
            )

            ans += (
                f"- **Trailing P/E:** "
                f"{val.get('trailing_pe', 'N/A')}\n"
            )

            ans += (
                f"- **Forward P/E:** "
                f"{val.get('forward_pe', 'N/A')}\n"
            )

            ans += (
                f"- **PEG Ratio:** "
                f"{val.get('peg_ratio', 'N/A')}\n"
            )

            ans += (
                f"- **Price / Sales:** "
                f"{val.get('price_to_sales', 'N/A')}x\n"
            )

            ans += (
                f"- **EV / EBITDA:** "
                f"{val.get('ev_to_ebitda', 'N/A')}x\n\n"
            )

            ans += (
                f"**Verdict:** "
                f"{score.get('bear_thesis')}"
                f"if (val.get('trailing_pe') or 0) > 30 "
                f"else score.get('bull_thesis')}"
            )

            return {
                "answer": ans
            }


        # PROFITABILITY
        elif (
            "margin" in q_lower
            or "profit" in q_lower
            or "roe" in q_lower
        ):

            ans = (
                f"**Profitability & Efficiency for "
                f"{profile.get('name')}:**\n\n"
            )

            ans += (
                f"- **Gross Margin:** "
                f"{prof.get('gross_margin', 0) * 100:.2f}%\n"
            )

            ans += (
                f"- **Operating Margin:** "
                f"{prof.get('operating_margin', 0) * 100:.2f}%\n"
            )

            ans += (
                f"- **Net Profit Margin:** "
                f"{prof.get('profit_margin', 0) * 100:.2f}%\n"
            )

            ans += (
                f"- **Return on Equity (ROE):** "
                f"{prof.get('return_on_equity', 0) * 100:.2f}%\n\n"
            )

            ans += (
                f"{score.get('bull_thesis')}"
            )

            return {
                "answer": ans
            }


        # GENERAL SUMMARY
        else:

            ans = (
                f"**Analysis Summary for "
                f"{profile.get('name')} "
                f"({profile.get('symbol')}):**\n\n"
            )

            ans += (
                f"- **Health Score:** "
                f"{score.get('overall_score')}/100 "
                f"(Grade {score.get('grade')})\n"
            )

            ans += (
                f"- **Consensus:** "
                f"{targets.get('recommendation_key', 'N/A').upper()} "
                f"with mean target "
                f"{price.get('currency', '$')}"
                f"{targets.get('target_mean_price', 'N/A')}\n"
            )

            ans += (
                f"- **Bull Thesis:** "
                f"{score.get('bull_thesis')}\n"
            )

            ans += (
                f"- **Bear Thesis:** "
                f"{score.get('bear_thesis')}\n"
            )

            return {
                "answer": ans
            }


    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# --------------------------------------------------
# WEBSITE ROOT
# --------------------------------------------------

@app.get("/")
async def get_index():

    index_file = os.path.join(
        STATIC_DIR,
        "index.html"
    )

    if os.path.exists(index_file):

        with open(
            index_file,
            "r",
            encoding="utf-8"
        ) as f:

            return HTMLResponse(
                content=f.read()
            )

    return HTMLResponse(
        "<h1>Company Analyzer Web UI Loading...</h1>"
    )


# --------------------------------------------------
# STATIC FILES
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)
