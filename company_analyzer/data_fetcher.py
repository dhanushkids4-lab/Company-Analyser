import math
import requests
import yfinance as yf
from typing import Dict, Any, Optional


class CompanyDataFetcher:
    """Fetches market data and financial information with graceful fallbacks."""

    @staticmethod
    def _clean_number(value):
        """Convert NaN values to None."""
        if value is None:
            return None

        try:
            if isinstance(value, float) and math.isnan(value):
                return None
        except Exception:
            pass

        return value

    @staticmethod
    def resolve_ticker(query: str) -> Dict[str, str]:
        """
        Resolves a company name or ticker to a ticker symbol.
        Falls back to the supplied text as an uppercase ticker.
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
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            }

            response = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                quotes = data.get("quotes", [])

                equity_quotes = [
                    quote
                    for quote in quotes
                    if quote.get("quoteType")
                    in ("EQUITY", "ETF")
                ]

                target = (
                    equity_quotes[0]
                    if equity_quotes
                    else (
                        quotes[0]
                        if quotes
                        else None
                    )
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

        # Track what Yahoo endpoints successfully returned.
        data_status = {
            "fast_info": False,
            "history": False,
            "info": False,
            "income_statement": False,
            "errors": []
        }

        # --------------------------------------------------
        # FAST INFO
        # --------------------------------------------------

        fast_info = {}

        try:
            fast_info = dict(ticker.fast_info)
            data_status["fast_info"] = True

        except Exception as e:
            message = (
                f"Fast info unavailable for {symbol}: {e}"
            )

            print(message)
            data_status["errors"].append(message)

        # --------------------------------------------------
        # PRICE HISTORY
        # --------------------------------------------------

        history_df = None

        try:
            history_df = ticker.history(
                period="1y",
                auto_adjust=False
            )

            if (
                history_df is not None
                and not history_df.empty
            ):
                data_status["history"] = True

        except Exception as e:
            message = (
                f"Price history unavailable for {symbol}: {e}"
            )

            print(message)
            data_status["errors"].append(message)

        # --------------------------------------------------
        # FULL INFO
        #
        # This endpoint can fail with Yahoo 401/429.
        # The rest of the app continues using other sources.
        # --------------------------------------------------

        info = {}

        try:
            info = ticker.info or {}

            if info:
                data_status["info"] = True

        except Exception as e:
            message = (
                f"Yahoo Finance info error for "
                f"{symbol}: {e}"
            )

            print(message)
            data_status["errors"].append(message)

            info = {}

        # --------------------------------------------------
        # CALCULATE PRICE FROM HISTORY
        # --------------------------------------------------

        history_last_price = None
        history_high = None
        history_low = None

        if (
            history_df is not None
            and not history_df.empty
        ):

            try:
                history_last_price = cls._clean_number(
                    float(history_df["Close"].iloc[-1])
                )
            except Exception:
                pass

            try:
                history_high = cls._clean_number(
                    float(history_df["High"].max())
                )
            except Exception:
                pass

            try:
                history_low = cls._clean_number(
                    float(history_df["Low"].min())
                )
            except Exception:
                pass

        # --------------------------------------------------
        # CURRENT PRICE
        # --------------------------------------------------

        current_price = (
            cls._clean_number(
                fast_info.get("last_price")
            )
            or history_last_price
            or cls._clean_number(
                info.get("currentPrice")
            )
            or cls._clean_number(
                info.get("regularMarketPrice")
            )
            or cls._clean_number(
                info.get("previousClose")
            )
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

            "full_time_employees": cls._clean_number(
                info.get("fullTimeEmployees")
            ),

            "currency": (
                info.get("currency")
                or fast_info.get("currency")
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
        # MARKET & PRICE
        # --------------------------------------------------

        price_stats = {
            "current_price": current_price,

            "currency": profile["currency"],

            "market_cap": (
                cls._clean_number(
                    fast_info.get("market_cap")
                )
                or cls._clean_number(
                    info.get("marketCap")
                )
            ),

            "enterprise_value": cls._clean_number(
                info.get("enterpriseValue")
            ),

            "fifty_two_week_high": (
                cls._clean_number(
                    fast_info.get("year_high")
                )
                or history_high
                or cls._clean_number(
                    info.get("fiftyTwoWeekHigh")
                )
            ),

            "fifty_two_week_low": (
                cls._clean_number(
                    fast_info.get("year_low")
                )
                or history_low
                or cls._clean_number(
                    info.get("fiftyTwoWeekLow")
                )
            ),

            "fifty_day_average": (
                cls._clean_number(
                    fast_info.get(
                        "fifty_day_average"
                    )
                )
                or cls._clean_number(
                    info.get("fiftyDayAverage")
                )
            ),

            "two_hundred_day_average": (
                cls._clean_number(
                    fast_info.get(
                        "two_hundred_day_average"
                    )
                )
                or cls._clean_number(
                    info.get(
                        "twoHundredDayAverage"
                    )
                )
            ),

            "beta": cls._clean_number(
                info.get("beta")
            ),

            "shares_outstanding": (
                cls._clean_number(
                    fast_info.get("shares")
                )
                or cls._clean_number(
                    info.get(
                        "sharesOutstanding"
                    )
                )
            ),

            "float_shares": cls._clean_number(
                info.get("floatShares")
            ),

            "short_ratio": cls._clean_number(
                info.get("shortRatio")
            )
        }

        # --------------------------------------------------
        # VALUATION
        # --------------------------------------------------

        valuation = {
            "trailing_pe": cls._clean_number(
                info.get("trailingPE")
            ),

            "forward_pe": cls._clean_number(
                info.get("forwardPE")
            ),

            "peg_ratio": cls._clean_number(
                info.get("pegRatio")
            ),

            "price_to_book": cls._clean_number(
                info.get("priceToBook")
            ),

            "price_to_sales": cls._clean_number(
                info.get(
                    "priceToSalesTrailing12Months"
                )
            ),

            "ev_to_ebitda": cls._clean_number(
                info.get(
                    "enterpriseToEbitda"
                )
            ),

            "ev_to_revenue": cls._clean_number(
                info.get(
                    "enterpriseToRevenue"
                )
            ),

            "book_value": cls._clean_number(
                info.get("bookValue")
            )
        }

        # --------------------------------------------------
        # PROFITABILITY
        # --------------------------------------------------

        revenue_ttm = cls._clean_number(
            info.get("totalRevenue")
        )

        profitability = {
            "revenue_ttm": revenue_ttm,

            "revenue_growth_yoy": cls._clean_number(
                info.get("revenueGrowth")
            ),

            "gross_margin": cls._clean_number(
                info.get("grossMargins")
            ),

            "operating_margin": cls._clean_number(
                info.get("operatingMargins")
            ),

            "profit_margin": cls._clean_number(
                info.get("profitMargins")
            ),

            "ebitda": cls._clean_number(
                info.get("ebitda")
            ),

            "return_on_equity": cls._clean_number(
                info.get("returnOnEquity")
            ),

            "return_on_assets": cls._clean_number(
                info.get("returnOnAssets")
            ),

            "earnings_growth_yoy": cls._clean_number(
                info.get("earningsGrowth")
            )
        }

        # --------------------------------------------------
        # BALANCE SHEET
        # --------------------------------------------------

        total_cash = cls._clean_number(
            info.get("totalCash")
        )

        total_debt = cls._clean_number(
            info.get("totalDebt")
        )

        net_debt = None

        if (
            total_cash is not None
            and total_debt is not None
        ):
            net_debt = (
                total_debt - total_cash
            )

        balance_sheet = {
            "total_cash": total_cash,
            "total_debt": total_debt,
            "net_debt": net_debt,

            "debt_to_equity": cls._clean_number(
                info.get("debtToEquity")
            ),

            "current_ratio": cls._clean_number(
                info.get("currentRatio")
            ),

            "quick_ratio": cls._clean_number(
                info.get("quickRatio")
            )
        }

        # --------------------------------------------------
        # CASH FLOW
        # --------------------------------------------------

        operating_cash_flow = cls._clean_number(
            info.get("operatingCashflow")
        )

        free_cash_flow = cls._clean_number(
            info.get("freeCashflow")
        )

        fcf_margin = None

        if (
            free_cash_flow is not None
            and revenue_ttm not in (
                None,
                0
            )
        ):
            fcf_margin = (
                free_cash_flow / revenue_ttm
            )

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
            "dividend_rate": cls._clean_number(
                info.get("dividendRate")
            ),

            "dividend_yield": cls._clean_number(
                info.get("dividendYield")
            ),

            "payout_ratio": cls._clean_number(
                info.get("payoutRatio")
            ),

            "five_year_avg_dividend_yield": (
                cls._clean_number(
                    info.get(
                        "fiveYearAvgDividendYield"
                    )
                )
            )
        }

        # --------------------------------------------------
        # ANALYST TARGETS
        # --------------------------------------------------

        analyst_targets = {
            "target_mean_price": (
                cls._clean_number(
                    info.get(
                        "targetMeanPrice"
                    )
                )
            ),

            "target_high_price": (
                cls._clean_number(
                    info.get(
                        "targetHighPrice"
                    )
                )
            ),

            "target_low_price": (
                cls._clean_number(
                    info.get(
                        "targetLowPrice"
                    )
                )
            ),

            "target_median_price": (
                cls._clean_number(
                    info.get(
                        "targetMedianPrice"
                    )
                )
            ),

            "recommendation_key": info.get(
                "recommendationKey"
            ),

            "number_of_analysts": (
                cls._clean_number(
                    info.get(
                        "numberOfAnalystOpinions"
                    )
                )
            )
        }

        # --------------------------------------------------
        # FINANCIAL HISTORY
        # --------------------------------------------------

        financial_history = []

        try:
            stmt = ticker.income_stmt

            if (
                stmt is not None
                and not stmt.empty
            ):

                data_status[
                    "income_statement"
                ] = True

                for col in stmt.columns[:4]:

                    year_str = (
                        str(col.year)
                        if hasattr(col, "year")
                        else str(col)[:10]
                    )

                    def get_value(row_name):
                        if row_name not in stmt.index:
                            return None

                        value = stmt.loc[
                            row_name,
                            col
                        ]

                        try:
                            if math.isnan(
                                float(value)
                            ):
                                return None

                            return float(value)

                        except Exception:
                            return None

                    financial_history.append({
                        "period": year_str,

                        "revenue": get_value(
                            "Total Revenue"
                        ),

                        "gross_profit": get_value(
                            "Gross Profit"
                        ),

                        "operating_income": get_value(
                            "Operating Income"
                        ),

                        "net_income": get_value(
                            "Net Income"
                        )
                    })

        except Exception as e:

            message = (
                f"Income statement unavailable "
                f"for {symbol}: {e}"
            )

            print(message)

            data_status[
                "errors"
            ].append(message)

        # --------------------------------------------------
        # RETURN ALL DATA
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

            "history": financial_history,

            "data_status": data_status
        }
