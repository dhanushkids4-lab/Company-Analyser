from typing import Dict, Any, List


class FinancialScorer:
    """Evaluates company health, calculates score & grade, and generates thesis & risk flags."""

    @classmethod
    def evaluate(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        val = data.get("valuation", {})
        prof = data.get("profitability", {})
        bs = data.get("balance_sheet", {})
        cf = data.get("cash_flow", {})
        price = data.get("price_stats", {})
        targets = data.get("analyst_targets", {})

        strengths: List[str] = []
        risks: List[str] = []

        # Sub-scores
        solvency_score = 0
        profitability_score = 0
        growth_score = 0
        valuation_score = 0

        # =====================================================
        # 1. SOLVENCY & LIQUIDITY (MAX 25)
        # =====================================================

        cur_ratio = bs.get("current_ratio")

        if cur_ratio is not None:
            if cur_ratio >= 1.5:
                solvency_score += 10
                strengths.append(
                    f"Healthy liquidity buffer (Current Ratio: {cur_ratio:.2f})"
                )
            elif cur_ratio >= 1.0:
                solvency_score += 7
            else:
                solvency_score += 2
                risks.append(
                    f"Tight short-term liquidity (Current Ratio: {cur_ratio:.2f} < 1.0)"
                )
        else:
            risks.append("Current liquidity ratio unavailable for analysis")

        de_ratio = bs.get("debt_to_equity")

        if de_ratio is not None:
            if de_ratio <= 50:
                solvency_score += 10
                strengths.append(
                    f"Conservative leverage (Debt/Equity: {de_ratio:.1f}%)"
                )
            elif de_ratio <= 100:
                solvency_score += 7
                risks.append(
                    f"Moderate leverage (Debt/Equity: {de_ratio:.1f}%)"
                )
            elif de_ratio <= 200:
                solvency_score += 4
                risks.append(
                    f"Elevated debt load (Debt/Equity: {de_ratio:.1f}%)"
                )
            else:
                solvency_score += 1
                risks.append(
                    f"Highly leveraged capital structure (Debt/Equity: {de_ratio:.1f}%)"
                )
        else:
            risks.append("Debt-to-equity data unavailable")

        net_debt = bs.get("net_debt")
        total_cash = bs.get("total_cash")

        if net_debt is not None:
            if net_debt < 0:
                solvency_score += 5
                strengths.append(
                    "Net cash position (Cash exceeds total debt)"
                )
            elif net_debt > 0:
                solvency_score += 2

                if total_cash is not None and total_cash > 0:
                    risks.append(
                        "Company carries a net debt position"
                    )
        elif total_cash is not None and total_cash > 0:
            solvency_score += 2


        # =====================================================
        # 2. PROFITABILITY & RETURNS (MAX 25)
        # =====================================================

        net_margin = prof.get("profit_margin")

        if net_margin is not None:
            if net_margin >= 0.20:
                profitability_score += 10
                strengths.append(
                    f"High net profit margin ({net_margin * 100:.1f}%)"
                )
            elif net_margin >= 0.10:
                profitability_score += 7
                strengths.append(
                    f"Solid net profit margin ({net_margin * 100:.1f}%)"
                )
            elif net_margin > 0:
                profitability_score += 4
            else:
                risks.append(
                    f"Unprofitable on a net income basis (Margin: {net_margin * 100:.1f}%)"
                )
        else:
            risks.append("Net profit margin data unavailable")

        roe = prof.get("return_on_equity")

        if roe is not None:
            if roe >= 0.20:
                profitability_score += 10
                strengths.append(
                    f"Exceptional capital efficiency (ROE: {roe * 100:.1f}%)"
                )
            elif roe >= 0.12:
                profitability_score += 7
                strengths.append(
                    f"Healthy Return on Equity (ROE: {roe * 100:.1f}%)"
                )
            elif roe > 0:
                profitability_score += 4
            else:
                risks.append(
                    f"Negative Return on Equity ({roe * 100:.1f}%)"
                )
        else:
            risks.append("Return on Equity data unavailable")

        fcf = cf.get("free_cash_flow")

        if fcf is not None:
            if fcf > 0:
                profitability_score += 5
                strengths.append(
                    "Positive Free Cash Flow generation"
                )
            elif fcf < 0:
                risks.append(
                    "Negative Free Cash Flow (cash burn)"
                )
            else:
                risks.append(
                    "Free Cash Flow is neutral or near zero"
                )
        else:
            risks.append(
                "Free Cash Flow data unavailable"
            )


        # =====================================================
        # 3. GROWTH & MOMENTUM (MAX 25)
        # =====================================================

        rev_growth = prof.get("revenue_growth_yoy")

        if rev_growth is not None:
            if rev_growth >= 0.20:
                growth_score += 12
                strengths.append(
                    f"Rapid top-line growth (Revenue YoY: +{rev_growth * 100:.1f}%)"
                )
            elif rev_growth >= 0.08:
                growth_score += 9
                strengths.append(
                    f"Steady revenue expansion (Revenue YoY: +{rev_growth * 100:.1f}%)"
                )
            elif rev_growth >= 0:
                growth_score += 5
            else:
                growth_score += 1
                risks.append(
                    f"Top-line contraction (Revenue YoY: {rev_growth * 100:.1f}%)"
                )
        else:
            risks.append(
                "Revenue growth data unavailable — growth momentum cannot be fully assessed"
            )

        earn_growth = prof.get("earnings_growth_yoy")

        if earn_growth is not None:
            if earn_growth >= 0.15:
                growth_score += 13
                strengths.append(
                    f"Robust earnings expansion (Earnings YoY: +{earn_growth * 100:.1f}%)"
                )
            elif earn_growth >= 0.05:
                growth_score += 8
            elif earn_growth >= 0:
                growth_score += 4
            else:
                growth_score += 1
                risks.append(
                    f"Earnings contraction YoY ({earn_growth * 100:.1f}%)"
                )
        else:
            risks.append(
                "Earnings growth data unavailable — earnings momentum cannot be fully assessed"
            )


        # =====================================================
        # 4. VALUATION & PRICE DISCIPLINE (MAX 25)
        # =====================================================

        trailing_pe = val.get("trailing_pe")
        forward_pe = val.get("forward_pe")
        peg = val.get("peg_ratio")

        valuation_metric_found = False

        if peg is not None and peg > 0:
            valuation_metric_found = True

            if peg <= 1.2:
                valuation_score += 10
                strengths.append(
                    f"Attractive growth valuation (PEG: {peg:.2f})"
                )
            elif peg <= 2.0:
                valuation_score += 7
            elif peg > 3.0:
                valuation_score += 2
                risks.append(
                    f"Premium PEG valuation multiple ({peg:.2f})"
                )
            else:
                valuation_score += 4

        elif forward_pe is not None and forward_pe > 0:
            valuation_metric_found = True

            if forward_pe <= 15:
                valuation_score += 10
                strengths.append(
                    f"Favorable forward valuation (Forward P/E: {forward_pe:.1f}x)"
                )
            elif forward_pe <= 25:
                valuation_score += 7
            elif forward_pe > 40:
                valuation_score += 2
                risks.append(
                    f"Elevated Forward P/E multiple ({forward_pe:.1f}x)"
                )
            else:
                valuation_score += 4

        elif trailing_pe is not None and trailing_pe > 0:
            valuation_metric_found = True

            if trailing_pe <= 15:
                valuation_score += 10
                strengths.append(
                    f"Attractive earnings valuation (P/E: {trailing_pe:.1f}x)"
                )
            elif trailing_pe <= 25:
                valuation_score += 7
            elif trailing_pe > 40:
                valuation_score += 2
                risks.append(
                    f"Elevated earnings valuation (P/E: {trailing_pe:.1f}x)"
                )
            else:
                valuation_score += 4

        if not valuation_metric_found:
            risks.append(
                "Key valuation metrics are unavailable"
            )


        # =====================================================
        # ANALYST TARGET UPSIDE
        # =====================================================

        cur_p = price.get("current_price")
        tgt_p = targets.get("target_mean_price")

        if (
            cur_p is not None
            and tgt_p is not None
            and cur_p > 0
            and tgt_p > 0
        ):
            upside = (tgt_p - cur_p) / cur_p

            if upside >= 0.20:
                valuation_score += 15
                strengths.append(
                    f"Wall Street target implies +{upside * 100:.1f}% potential upside"
                )
            elif upside >= 0.05:
                valuation_score += 10
                strengths.append(
                    f"Wall Street target implies +{upside * 100:.1f}% potential upside"
                )
            elif upside < -0.05:
                valuation_score += 2
                risks.append(
                    f"Trading above mean analyst target (Implied downside: {abs(upside) * 100:.1f}%)"
                )
            else:
                valuation_score += 6
        else:
            risks.append(
                "Analyst target data unavailable — upside/downside cannot be assessed"
            )


        # =====================================================
        # GENERIC WATCHPOINTS
        # =====================================================

        # Even strong companies should have meaningful watchpoints.

        if not risks:
            risks.append(
                "Future performance remains sensitive to macroeconomic conditions and industry demand"
            )

        if len(risks) < 2:
            risks.append(
                "Competitive pressure and changes in market conditions could affect future margins"
            )

        if trailing_pe is not None and trailing_pe > 25:
            risk_text = (
                f"Valuation remains sensitive to earnings expectations (P/E: {trailing_pe:.1f}x)"
            )

            if risk_text not in risks:
                risks.append(risk_text)

        if rev_growth is not None and rev_growth < 0.05:
            risks.append(
                "Limited revenue growth could constrain future valuation expansion"
            )


        # =====================================================
        # FINAL SCORE
        # =====================================================

        total_score = (
            solvency_score
            + profitability_score
            + growth_score
            + valuation_score
        )

        total_score = min(100, max(0, round(total_score)))

        grade = cls._score_to_grade(total_score)


        # Generate Bull / Bear Thesis
        bull_thesis = cls._generate_bull_thesis(
            data,
            strengths,
            total_score
        )

        bear_thesis = cls._generate_bear_thesis(
            data,
            risks,
            total_score
        )


        return {
            "overall_score": total_score,
            "grade": grade,
            "breakdown": {
                "solvency": solvency_score,
                "profitability": profitability_score,
                "growth": growth_score,
                "valuation": valuation_score
            },
            "strengths": strengths[:6],
            "risks": risks[:6],
            "bull_thesis": bull_thesis,
            "bear_thesis": bear_thesis
        }


    @staticmethod
    def _score_to_grade(score: int) -> str:
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "A-"
        elif score >= 75:
            return "B+"
        elif score >= 70:
            return "B"
        elif score >= 65:
            return "B-"
        elif score >= 60:
            return "C+"
        elif score >= 50:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"


    @staticmethod
    def _generate_bull_thesis(
        data: Dict[str, Any],
        strengths: List[str],
        score: int
    ) -> str:

        name = data.get(
            "profile",
            {}
        ).get(
            "name",
            "The company"
        )

        prof = data.get(
            "profitability",
            {}
        )

        rev_g = prof.get(
            "revenue_growth_yoy"
        )

        pm = prof.get(
            "profit_margin"
        )

        parts = [
            f"{name} demonstrates solid underlying fundamentals backed by an overall health score of {score}/100."
        ]

        if pm is not None and pm >= 0.15:
            parts.append(
                f"High profit margins ({pm * 100:.1f}%) provide pricing power and defensible economic moats."
            )

        if rev_g is not None and rev_g > 0.10:
            parts.append(
                f"Top-line expansion (+{rev_g * 100:.1f}% YoY) showcases sustained commercial demand."
            )

        if strengths:
            parts.append(
                "Key drivers include: "
                + "; ".join(strengths[:3])
                + "."
            )

        return " ".join(parts)


    @staticmethod
    def _generate_bear_thesis(
        data: Dict[str, Any],
        risks: List[str],
        score: int
    ) -> str:

        name = data.get(
            "profile",
            {}
        ).get(
            "name",
            "The company"
        )

        val = data.get(
            "valuation",
            {}
        )

        pe = (
            val.get("forward_pe")
            or val.get("trailing_pe")
        )

        parts = []

        if risks:
            parts.append(
                f"Key watchpoints for {name} include: "
                + "; ".join(risks[:3])
                + "."
            )
        else:
            parts.append(
                f"{name} remains exposed to macroeconomic cyclicality, sector competition, and market multiple compression."
            )

        if pe is not None and pe > 30:
            parts.append(
                f"A high earnings multiple ({pe:.1f}x) leaves less margin of safety if future earnings or guidance disappoint."
            )

        return " ".join(parts)
