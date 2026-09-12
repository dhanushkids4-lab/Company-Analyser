import os
import json
import requests
from typing import Dict, Any, Optional


class LLMAnalyzer:
    """Provides LLM-powered strategic and financial synthesis with automatic fallback."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self.model = model

        # Auto-detect default base URL and model if not specified
        if not self.base_url:
            if os.getenv("GROQ_API_KEY"):
                self.base_url = "https://api.groq.com/openai/v1"
                self.model = self.model or "llama-3.3-70b-versatile"
            elif os.getenv("OPENROUTER_API_KEY"):
                self.base_url = "https://openrouter.ai/api/v1"
                self.model = self.model or "meta-llama/llama-3.3-70b-instruct"
            else:
                self.base_url = "https://api.openai.com/v1"
                self.model = self.model or "gpt-4o-mini"

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_analysis(self, company_data: Dict[str, Any], score_data: Dict[str, Any]) -> str:
        """
        Synthesizes an executive analyst memo using the configured LLM, or fallback if unavailable.
        """
        if not self.is_available:
            return self._generate_fallback_memo(company_data, score_data)

        prompt = self._build_prompt(company_data, score_data)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a Senior Wall Street Equity Research Analyst. "
                            "Write a crisp, institutional-grade executive analysis memo based strictly on the provided financial stats. "
                            "Avoid fluff. Use bullet points and clear sections:\n"
                            "1. Business Moat & Market Position\n"
                            "2. Financial Health & Margins\n"
                            "3. Valuation Reality Check\n"
                            "4. Catalysts vs Headwinds\n"
                            "5. Final Verdict (Overweight / Equal-Weight / Underweight with target rationale)."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2
            }

            endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
            res = requests.post(endpoint, headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                result = res.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                return self._generate_fallback_memo(company_data, score_data)
        except Exception:
            return self._generate_fallback_memo(company_data, score_data)

    def _build_prompt(self, company_data: Dict[str, Any], score_data: Dict[str, Any]) -> str:
        profile = company_data.get("profile", {})
        price = company_data.get("price_stats", {})
        val = company_data.get("valuation", {})
        prof = company_data.get("profitability", {})
        bs = company_data.get("balance_sheet", {})
        cf = company_data.get("cash_flow", {})
        targets = company_data.get("analyst_targets", {})

        return f"""
Analyze the following company:
- Company: {profile.get('name')} ({profile.get('symbol')})
- Sector / Industry: {profile.get('sector')} | {profile.get('industry')}
- Current Price: {price.get('current_price')} {price.get('currency')} (52W Range: {price.get('fifty_two_week_low')} - {price.get('fifty_two_week_high')})
- Market Cap: {price.get('market_cap')} | Enterprise Value: {price.get('enterprise_value')}
- Valuation: Trailing P/E: {val.get('trailing_pe')}, Forward P/E: {val.get('forward_pe')}, PEG: {val.get('peg_ratio')}, P/S: {val.get('price_to_sales')}, EV/EBITDA: {val.get('ev_to_ebitda')}
- Profitability: Revenue TTM: {prof.get('revenue_ttm')}, YoY Revenue Growth: {prof.get('revenue_growth_yoy')}, Gross Margin: {prof.get('gross_margin')}, Operating Margin: {prof.get('operating_margin')}, Net Margin: {prof.get('profit_margin')}, ROE: {prof.get('return_on_equity')}
- Solvency: Total Cash: {bs.get('total_cash')}, Total Debt: {bs.get('total_debt')}, Debt/Equity: {bs.get('debt_to_equity')}, Current Ratio: {bs.get('current_ratio')}
- Cash Flow: FCF: {cf.get('free_cash_flow')}, Operating Cash Flow: {cf.get('operating_cash_flow')}
- Analyst Consensus: Mean Target: {targets.get('target_mean_price')}, Recommendation: {targets.get('recommendation_key')}, Analysts: {targets.get('number_of_analysts')}
- Algorithmic Health Score: {score_data.get('overall_score')}/100 (Grade: {score_data.get('grade')})
- Detected Strengths: {', '.join(score_data.get('strengths', []))}
- Detected Risks: {', '.join(score_data.get('risks', []))}
"""

    def _generate_fallback_memo(self, company_data: Dict[str, Any], score_data: Dict[str, Any]) -> str:
        profile = company_data.get("profile", {})
        val = company_data.get("valuation", {})
        prof = company_data.get("profitability", {})
        price = company_data.get("price_stats", {})
        targets = company_data.get("analyst_targets", {})
        cf = company_data.get("cash_flow", {})

        name = profile.get("name", "The Company")
        ticker = profile.get("symbol", "N/A")
        grade = score_data.get("grade", "N/A")
        score = score_data.get("overall_score", 0)

        rev_g_str = f"{prof.get('revenue_growth_yoy')*100:.1f}%" if prof.get('revenue_growth_yoy') is not None else "N/A"
        pm_str = f"{prof.get('profit_margin')*100:.1f}%" if prof.get('profit_margin') is not None else "N/A"
        roe_str = f"{prof.get('return_on_equity')*100:.1f}%" if prof.get('return_on_equity') is not None else "N/A"
        fcf_val = cf.get("free_cash_flow")
        curr_sym = "$" if price.get("currency") == "USD" else f"{price.get('currency', '')} "
        fcf_str = f"{curr_sym}{fcf_val:,.0f}" if fcf_val is not None else "N/A"
        rec_str = str(targets.get("recommendation_key", "N/A")).upper().replace("_", " ")

        pe_str = f"{val.get('trailing_pe'):.2f}x" if val.get('trailing_pe') else "N/A"
        fpe_str = f"{val.get('forward_pe'):.2f}x" if val.get('forward_pe') else "N/A"
        ev_ebitda_str = f"{val.get('ev_to_ebitda'):.2f}x" if val.get('ev_to_ebitda') else "N/A"
        tgt_val = targets.get("target_mean_price")
        tgt_str = f"{price.get('currency', 'USD')} {tgt_val:.2f}" if tgt_val else "N/A"

        summary_preview = profile.get("summary", "")[:280]
        if not summary_preview:
            summary_preview = f"Operating in the {profile.get('industry', 'global')} industry."

        lines = [
            f"### Executive Analysis Memo: {name} ({ticker})",
            f"**Overall Health Grade:** {grade} ({score}/100)",
            "",
            "#### 1. Fundamental Overview",
            f"- **Core Business:** {summary_preview}...",
            f"- **Sector / Industry:** {profile.get('sector', 'N/A')} | {profile.get('industry', 'N/A')}",
            "",
            "#### 2. Key Financial Highlights & Margins",
            f"- **Top-Line Growth:** Revenue YoY: {rev_g_str}",
            f"- **Profitability:** Net Margin: {pm_str} | ROE: {roe_str}",
            f"- **Cash Generation:** Free Cash Flow: {fcf_str}",
            "",
            "#### 3. Valuation & Market Stance",
            f"- **Multiples:** Trailing P/E: {pe_str} | Forward P/E: {fpe_str} | EV/EBITDA: {ev_ebitda_str}",
            f"- **Wall Street Consensus:** {rec_str} (Target: {tgt_str})",
            "",
            "#### 4. Bull vs. Bear Drivers",
            f"- **Bull Case:** {score_data.get('bull_thesis', 'Solid position.')}",
            f"- **Bear Case:** {score_data.get('bear_thesis', 'Market headwinds.')}"
        ]
        return "\n".join(lines)
