import requests
import yfinance as yf
from typing import Dict, Any, Optional, List


class CompanyDataFetcher:
    """Fetches real-time market data, valuation metrics, and financial statements."""

    @staticmethod
    def resolve_ticker(query: str) -> Optional[Dict[str, str]]:
        """
        Resolves a company name or ticker search query to a ticker symbol using Yahoo Finance.
        Returns a dict with 'symbol', 'name', 'exchange', 'quoteType' if found.
        """
        cleaned = query.strip()
        
        # Search via Yahoo Finance Search API first to get reliable symbol resolution
        try:
            url = f"https://query2.finance.yahoo.com/v1/finance/search?q={requests.utils.quote(cleaned)}&quotesCount=5&newsCount=0"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                quotes = data.get("quotes", [])
                equity_quotes = [q for q in quotes if q.get("quoteType") in ("EQUITY", "ETF")]
                target = equity_quotes[0] if equity_quotes else (quotes[0] if quotes else None)
                if target and target.get("symbol"):
                    return {
                        "symbol": target.get("symbol"),
                        "name": target.get("shortname") or target.get("longname") or target.get("symbol"),
                        "exchange": target.get("exchange", "Unknown"),
                        "quoteType": target.get("quoteType", "EQUITY")
                    }
        except Exception:
            pass

        return {"symbol": cleaned.upper(), "name": cleaned, "exchange": "Unknown", "quoteType": "EQUITY"}

    @classmethod
    def fetch_company_data(cls, symbol_or_name: str) -> Dict[str, Any]:
        """
        Fetches full company stats and returns structured data dictionary.
        """
        resolved = cls.resolve_ticker(symbol_or_name)
        symbol = resolved.get("symbol", symbol_or_name.upper())

       ticker = yf.Ticker(symbol)

       try:
        info = ticker.info or {}
       except Exception as e:
         print(f"Yahoo Finance info error for {symbol}: {e}")
         info = {}

        # Profile
        profile = {
            "symbol": symbol,
            "name": info.get("shortName") or info.get("longName") or resolved.get("name") or symbol,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "website": info.get("website", "N/A"),
            "full_time_employees": info.get("fullTimeEmployees"),
            "currency": info.get("currency", "USD"),
            "exchange": info.get("exchange", resolved.get("exchange", "N/A")),
            "summary": info.get("longBusinessSummary", "")
        }

        # Market & Price
      current_price = (
    fast_info.get("last_price")
    or info.get("currentPrice")
    or info.get("regularMarketPrice")
    or info.get("previousClose")
)
        price_stats = {
            "current_price": current_price,
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "beta": info.get("beta"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "short_ratio": info.get("shortRatio")
        }

        # Valuation Multiples
        valuation = {
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "ev_to_revenue": info.get("enterpriseToRevenue"),
            "book_value": info.get("bookValue")
        }

        # Financial Performance & Margins (TTM)
        revenue_ttm = info.get("totalRevenue")
        gross_margins = info.get("grossMargins")
        operating_margins = info.get("operatingMargins")
        profit_margins = info.get("profitMargins")
        ebitda = info.get("ebitda")

        profitability = {
            "revenue_ttm": revenue_ttm,
            "revenue_growth_yoy": info.get("revenueGrowth"),
            "gross_margin": gross_margins,
            "operating_margin": operating_margins,
            "profit_margin": profit_margins,
            "ebitda": ebitda,
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "earnings_growth_yoy": info.get("earningsGrowth")
        }

        # Balance Sheet & Solvency
        total_cash = info.get("totalCash")
        total_debt = info.get("totalDebt")
        net_debt = (total_debt - total_cash) if (total_debt is not None and total_cash is not None) else None

        balance_sheet = {
            "total_cash": total_cash,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio")
        }

        # Cash Flow
        operating_cash_flow = info.get("operatingCashflow")
        free_cash_flow = info.get("freeCashflow")
        fcf_margin = (free_cash_flow / revenue_ttm) if (free_cash_flow and revenue_ttm) else None

        cash_flow = {
            "operating_cash_flow": operating_cash_flow,
            "free_cash_flow": free_cash_flow,
            "fcf_margin": fcf_margin
        }

        # Dividends
        dividends = {
            "dividend_rate": info.get("dividendRate"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield")
        }

        # Analyst Consensus & Targets
        analyst_targets = {
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analysts": info.get("numberOfAnalystOpinions")
        }

        # Historical Trend Extraction
        history = []
        try:
            stmt = ticker.income_stmt
            if stmt is not None and not stmt.empty:
                for col in stmt.columns[:4]:  # last 4 periods
                    year_str = str(col.year) if hasattr(col, "year") else str(col)[:10]
                    rev = stmt.loc["Total Revenue", col] if "Total Revenue" in stmt.index else None
                    gp = stmt.loc["Gross Profit", col] if "Gross Profit" in stmt.index else None
                    op = stmt.loc["Operating Income", col] if "Operating Income" in stmt.index else None
                    ni = stmt.loc["Net Income", col] if "Net Income" in stmt.index else None
                    
                    history.append({
                        "period": year_str,
                        "revenue": float(rev) if rev is not None and not str(rev).lower() == 'nan' else None,
                        "gross_profit": float(gp) if gp is not None and not str(gp).lower() == 'nan' else None,
                        "operating_income": float(op) if op is not None and not str(op).lower() == 'nan' else None,
                        "net_income": float(ni) if ni is not None and not str(ni).lower() == 'nan' else None
                    })
        except Exception:
            pass

        return {
            "profile": profile,
            "price_stats": price_stats,
            "valuation": valuation,
            "profitability": profitability,
            "balance_sheet": balance_sheet,
            "cash_flow": cash_flow,
            "dividends": dividends,
            "analyst_targets": analyst_targets,
            "history": history
        }
