import requests
import yfinance as yf

from typing import Dict, Any, Optional


class CompanyDataFetcher:
    """Fetches market data and financial statements with fallbacks."""

    @staticmethod
    def resolve_ticker(query: str) -> Optional[Dict[str, str]]:
        """
        Resolves a company name or ticker search query.
        """

        cleaned = query.strip()

        try:
            url = (
                "https://query2.finance.yahoo.com/v1/finance/search"
                f"?q={requests.utils.quote(cleaned)}"
                "&quotesCount=5&newsCount=0"
            )

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
                )
            }

            res = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            if res.status_code == 200:
                data = res.json()

                quotes = data.get("quotes", [])

                equity_quotes = [
                    q for q in quotes
                    if q.get("quoteType") in ("EQUITY", "ETF")
                ]

                target = (
                    equity_quotes[0]
                    if equity_quotes
                    else (quotes[0] if quotes else None)
                )

                if target and target.get("symbol"):
                    return {
                        "symbol": target.get("symbol"),
                        "name": (
                            target.get("shortname")
                            or target.get("longname")
                            or target.get("symbol")
                        ),
                        "exchange": target.get(
                            "exchange",
                            "Unknown"
                        ),
                        "quoteType": target.get(
                            "quoteType",
                            "EQUITY"
                        )
                    }

        except Exception as e:
            print(f"Ticker search error: {e}")

        return {
            "symbol": cleaned.upper(),
            "name": cleaned,
            "exchange": "Unknown",
            "quoteType": "EQUITY"
        }

    @staticmethod
    def _safe_get(df, row_name, column):
        """
        Safely extract a value from a financial statement.
        """

        try:
            if (
                df is not None
                and not df.empty
                and row_name in df.index
            ):
                value = df.loc[row_name, column]

                if value is not None:
                    return float(value)

        except Exception:
            pass

        return None

    @classmethod
    def fetch_company_data(
        cls,
        symbol_or_name: str
    ) -> Dict[str, Any]:

        resolved = cls.resolve_ticker(symbol_or_name)

        symbol = resolved.get(
            "symbol",
            symbol_or_name.upper()
        )

        ticker = yf.Ticker(symbol)

        # --------------------------------------------------
        # FAST INFO
        # --------------------------------------------------

        try:
            fast_info = dict(ticker.fast_info)
        except Exception as e:
            print(f"Fast info error for {symbol}: {e}")
            fast_info = {}

        # --------------------------------------------------
        # REGULAR INFO
        # Optional because Yahoo may block this endpoint
        # --------------------------------------------------

        try:
            info = ticker.info or {}
        except Exception as e:
            print(
                f"Yahoo Finance info error for {symbol}: {e}"
            )
            info = {}

        # --------------------------------------------------
        # PRICE HISTORY FALLBACK
        # --------------------------------------------------

        try:
            price_history = ticker.history(
                period="1y",
                auto_adjust=False
            )
        except Exception as e:
            print(f"History error for {symbol}: {e}")
            price_history = None

        history_price = None
        fifty_two_week_high = None
        fifty_two_week_low = None

        try:
            if (
                price_history is not None
                and not price_history.empty
            ):
                history_price = float(
                    price_history["Close"].iloc[-1]
                )

                fifty_two_week_high = float(
                    price_history["High"].max()
                )

                fifty_two_week_low = float(
                    price_history["Low"].min()
                )

        except Exception:
            pass

        # --------------------------------------------------
        # FINANCIAL STATEMENTS
        # --------------------------------------------------

        try:
            income_stmt = ticker.income_stmt
        except Exception as e:
            print(f"Income statement error: {e}")
            income_stmt = None

        try:
            balance_sheet_stmt = ticker.balance_sheet
        except Exception as e:
            print(f"Balance sheet error: {e}")
            balance_sheet_stmt = None

        try:
            cashflow_stmt = ticker.cashflow
        except Exception as e:
            print(f"Cash flow error: {e}")
            cashflow_stmt = None

        # --------------------------------------------------
        # LATEST FINANCIAL PERIOD
        # --------------------------------------------------

        latest_income_col = None

        try:
            if (
                income_stmt is not None
                and not income_stmt.empty
            ):
                latest_income_col = income_stmt.columns[0]
        except Exception:
            pass

        latest_balance_col = None

        try:
            if (
                balance_sheet_stmt is not None
                and not balance_sheet_stmt.empty
            ):
                latest_balance_col = (
                    balance_sheet_stmt.columns[0]
                )
        except Exception:
            pass

        latest_cashflow_col = None

        try:
            if (
                cashflow_stmt is not None
                and not cashflow_stmt.empty
            ):
                latest_cashflow_col = (
                    cashflow_stmt.columns[0]
                )
        except Exception:
            pass

        # --------------------------------------------------
        # INCOME STATEMENT VALUES
        # --------------------------------------------------

        revenue = None
        gross_profit = None
        operating_income = None
        net_income = None

        if latest_income_col is not None:

            revenue = cls._safe_get(
                income_stmt,
                "Total Revenue",
                latest_income_col
            )

            gross_profit = cls._safe_get(
                income_stmt,
                "Gross Profit",
                latest_income_col
            )

            operating_income = cls._safe_get(
                income_stmt,
                "Operating Income",
                latest_income_col
            )

            net_income = cls._safe_get(
                income_stmt,
                "Net Income",
                latest_income_col
            )

        gross_margin = (
            gross_profit / revenue
            if gross_profit is not None
            and revenue not in (None, 0)
            else info.get("grossMargins")
        )

        operating_margin = (
            operating_income / revenue
            if operating_income is not None
            and revenue not in (None, 0)
            else info.get("operatingMargins")
        )

        profit_margin = (
            net_income / revenue
            if net_income is not None
            and revenue not in (None, 0)
            else info.get("profitMargins")
        )

        # --------------------------------------------------
        # BALANCE SHEET VALUES
        # --------------------------------------------------

        total_cash = None
        total_debt = None

        if latest_balance_col is not None:

            total_cash = (
                cls._safe_get(
                    balance_sheet_stmt,
                    "Cash Cash Equivalents And Short Term Investments",
                    latest_balance_col
                )
                or cls._safe_get(
                    balance_sheet_stmt,
                    "Cash And Cash Equivalents",
                    latest_balance_col
                )
                or cls._safe_get(
                    balance_sheet_stmt,
                    "Cash Financial",
                    latest_balance_col
                )
            )

            total_debt = (
                cls._safe_get(
                    balance_sheet_stmt,
                    "Total Debt",
                    latest_balance_col
                )
                or cls._safe_get(
                    balance_sheet_stmt,
                    "Long Term Debt",
                    latest_balance_col
                )
            )

        if total_cash is None:
            total_cash = info.get("totalCash")

        if total_debt is None:
            total_debt = info.get("totalDebt")

        net_debt = None

        if (
            total_debt is not None
            and total_cash is not None
        ):
            net_debt = total_debt - total_cash

        # --------------------------------------------------
        # CASH FLOW VALUES
        # --------------------------------------------------

        operating_cash_flow = None
        free_cash_flow = None

        if latest_cashflow_col is not None:

            operating_cash_flow = (
                cls._safe_get(
                    cashflow_stmt,
                    "Operating Cash Flow",
                    latest_cashflow_col
                )
            )

            free_cash_flow = (
                cls._safe_get(
                    cashflow_stmt,
                    "Free Cash Flow",
                    latest_cashflow_col
                )
            )

        if operating_cash_flow is None:
            operating_cash_flow = info.get(
                "operatingCashflow"
            )

        if free_cash_flow is None:
            free_cash_flow = info.get(
                "freeCashflow"
            )

        fcf_margin = None

        if (
            free_cash_flow is not None
            and revenue not in (None, 0)
        ):
            fcf_margin = free_cash_flow / revenue

        # --------------------------------------------------
        # PRICE
        # --------------------------------------------------

        current_price = (
            fast_info.get("lastPrice")
            or fast_info.get("last_price")
            or fast_info.get("regularMarketPrice")
            or info.get("currentPrice")
            or info.get("regularMarketPrice")
            or history_price
            or info.get("previousClose")
        )

        # --------------------------------------------------
        # PROFILE
        # --------------------------------------------------

        profile = {
            "symbol": symbol,

            "name": (
                info.get("shortName")
                or info.get("longName")
                or resolved.get("name")
                or symbol
            ),

            "sector": info.get(
                "sector",
                "N/A"
            ),

            "industry": info.get(
                "industry",
                "N/A"
            ),

            "country": info.get(
                "country",
                "N/A"
            ),

            "website": info.get(
                "website",
                "N/A"
            ),

            "full_time_employees": info.get(
                "fullTimeEmployees"
            ),

            "currency": (
                fast_info.get("currency")
                or info.get("currency")
                or "USD"
            ),

            "exchange": (
                info.get("exchange")
                or resolved.get("exchange")
                or "N/A"
            ),

            "summary": info.get(
                "longBusinessSummary",
                ""
            )
        }

        # --------------------------------------------------
        # PRICE STATS
        # --------------------------------------------------

        price_stats = {

            "current_price": current_price,

            "currency": profile["currency"],

            "market_cap": (
                fast_info.get("marketCap")
                or fast_info.get("market_cap")
                or info.get("marketCap")
            ),

            "enterprise_value": info.get(
                "enterpriseValue"
            ),

            "fifty_two_week_high": (
                fast_info.get("yearHigh")
                or fast_info.get("year_high")
                or info.get("fiftyTwoWeekHigh")
                or fifty_two_week_high
            ),

            "fifty_two_week_low": (
                fast_info.get("yearLow")
                or fast_info.get("year_low")
                or info.get("fiftyTwoWeekLow")
                or fifty_two_week_low
            ),

            "fifty_day_average": info.get(
                "fiftyDayAverage"
            ),

            "two_hundred_day_average": info.get(
                "twoHundredDayAverage"
            ),

            "beta": info.get("beta"),

            "shares_outstanding": (
                fast_info.get("shares")
                or fast_info.get("shares_outstanding")
                or info.get("sharesOutstanding")
            ),

            "float_shares": info.get(
                "floatShares"
            ),

            "short_ratio": info.get(
                "shortRatio"
            )
        }

        # --------------------------------------------------
        # VALUATION
        # --------------------------------------------------

        valuation = {

            "trailing_pe": info.get(
                "trailingPE"
            ),

            "forward_pe": info.get(
                "forwardPE"
            ),

            "peg_ratio": info.get(
                "pegRatio"
            ),

            "price_to_book": info.get(
                "priceToBook"
            ),

            "price_to_sales": info.get(
                "priceToSalesTrailing12Months"
            ),

            "ev_to_ebitda": info.get(
                "enterpriseToEbitda"
            ),

            "ev_to_revenue": info.get(
                "enterpriseToRevenue"
            ),

            "book_value": info.get(
                "bookValue"
            )
        }

        # --------------------------------------------------
        # PROFITABILITY
        # --------------------------------------------------

        profitability = {

            "revenue_ttm": (
                revenue
                or info.get("totalRevenue")
            ),

            "revenue_growth_yoy": info.get(
                "revenueGrowth"
            ),

            "gross_margin": gross_margin,

            "operating_margin": operating_margin,

            "profit_margin": profit_margin,

            "ebitda": info.get(
                "ebitda"
            ),

            "return_on_equity": info.get(
                "returnOnEquity"
            ),

            "return_on_assets": info.get(
                "returnOnAssets"
            ),

            "earnings_growth_yoy": info.get(
                "earningsGrowth"
            )
        }

        # --------------------------------------------------
        # BALANCE SHEET
        # --------------------------------------------------

        balance_sheet = {

            "total_cash": total_cash,

            "total_debt": total_debt,

            "net_debt": net_debt,

            "debt_to_equity": info.get(
                "debtToEquity"
            ),

            "current_ratio": info.get(
                "currentRatio"
            ),

            "quick_ratio": info.get(
                "quickRatio"
            )
        }

        # --------------------------------------------------
        # CASH FLOW
        # --------------------------------------------------

        cash_flow = {

            "operating_cash_flow": (
                operating_cash_flow
            ),

            "free_cash_flow": (
                free_cash_flow
            ),

            "fcf_margin": fcf_margin
        }

        # --------------------------------------------------
        # DIVIDENDS
        # --------------------------------------------------

        dividends = {

            "dividend_rate": info.get(
                "dividendRate"
            ),

            "dividend_yield": info.get(
                "dividendYield"
            ),

            "payout_ratio": info.get(
                "payoutRatio"
            ),

            "five_year_avg_dividend_yield": info.get(
                "fiveYearAvgDividendYield"
            )
        }

        # --------------------------------------------------
        # ANALYST TARGETS
        # --------------------------------------------------

        analyst_targets = {

            "target_mean_price": info.get(
                "targetMeanPrice"
            ),

            "target_high_price": info.get(
                "targetHighPrice"
            ),

            "target_low_price": info.get(
                "targetLowPrice"
            ),

            "target_median_price": info.get(
                "targetMedianPrice"
            ),

            "recommendation_key": info.get(
                "recommendationKey"
            ),

            "number_of_analysts": info.get(
                "numberOfAnalystOpinions"
            )
        }

        # --------------------------------------------------
        # HISTORICAL FINANCIAL DATA
        # --------------------------------------------------

        history = []

        try:

            if (
                income_stmt is not None
                and not income_stmt.empty
            ):

                for col in income_stmt.columns[:4]:

                    year_str = (
                        str(col.year)
                        if hasattr(col, "year")
                        else str(col)[:10]
                    )

                    rev = cls._safe_get(
                        income_stmt,
                        "Total Revenue",
                        col
                    )

                    gp = cls._safe_get(
                        income_stmt,
                        "Gross Profit",
                        col
                    )

                    op = cls._safe_get(
                        income_stmt,
                        "Operating Income",
                        col
                    )

                    ni = cls._safe_get(
                        income_stmt,
                        "Net Income",
                        col
                    )

                    history.append({

                        "period": year_str,

                        "revenue": rev,

                        "gross_profit": gp,

                        "operating_income": op,

                        "net_income": ni
                    })

        except Exception as e:
            print(f"Historical data error: {e}")

        # --------------------------------------------------
        # FINAL RESPONSE
        # --------------------------------------------------

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
