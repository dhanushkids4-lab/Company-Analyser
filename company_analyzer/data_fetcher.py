import math
import requests
import yfinance as yf

from typing import Dict, Any, Optional


class CompanyDataFetcher:
    """Fetches company market data and financial statements."""

    @staticmethod
    def safe_float(value):
        """Convert values to float safely."""
        try:
            if value is None:
                return None

            value = float(value)

            if math.isnan(value):
                return None

            return value
        except Exception:
            return None

    @staticmethod
    def safe_divide(a, b):
        """Safely divide two numbers."""
        try:
            if a is None or b is None:
                return None

            if b == 0:
                return None

            return a / b
        except Exception:
            return None

    @staticmethod
    def get_statement_value(statement, row_names, column=None):
        """
        Safely get a value from a Yahoo Finance statement.
        Tries multiple possible row names.
        """

        if statement is None or statement.empty:
            return None

        if isinstance(row_names, str):
            row_names = [row_names]

        for row_name in row_names:
            if row_name in statement.index:
                try:
                    if column is None:
                        if len(statement.columns) == 0:
                            continue

                        value = statement.loc[row_name, statement.columns[0]]
                    else:
                        value = statement.loc[row_name, column]

                    return CompanyDataFetcher.safe_float(value)

                except Exception:
                    pass

        return None

    @staticmethod
    def resolve_ticker(query: str) -> Dict[str, str]:
        """
        Resolves a company name or ticker to a Yahoo Finance symbol.
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

    @classmethod
    def fetch_company_data(
        cls,
        symbol_or_name: str
    ) -> Dict[str, Any]:

        # --------------------------------------------------
        # 1. Resolve company symbol
        # --------------------------------------------------

        resolved = cls.resolve_ticker(symbol_or_name)

        symbol = resolved.get(
            "symbol",
            symbol_or_name.upper()
        )

        ticker = yf.Ticker(symbol)

        # --------------------------------------------------
        # 2. Optional Yahoo info
        # --------------------------------------------------

        info = {}

        try:
            info = ticker.info or {}
        except Exception as e:
            print(
                f"Yahoo Finance info unavailable for "
                f"{symbol}: {e}"
            )

        # --------------------------------------------------
        # 3. Fast market information
        # --------------------------------------------------

        fast_info = {}

        try:
            fast_info = dict(ticker.fast_info)
        except Exception as e:
            print(
                f"Fast info unavailable for "
                f"{symbol}: {e}"
            )

        # --------------------------------------------------
        # 4. Price history fallback
        # --------------------------------------------------

        history = None

        try:
            history = ticker.history(
                period="1y",
                interval="1d",
                auto_adjust=False
            )
        except Exception as e:
            print(
                f"Price history unavailable for "
                f"{symbol}: {e}"
            )

        history_price = None
        history_high = None
        history_low = None

        try:
            if history is not None and not history.empty:

                close_series = history["Close"].dropna()

                if not close_series.empty:
                    history_price = cls.safe_float(
                        close_series.iloc[-1]
                    )

                high_series = history["High"].dropna()

                if not high_series.empty:
                    history_high = cls.safe_float(
                        high_series.max()
                    )

                low_series = history["Low"].dropna()

                if not low_series.empty:
                    history_low = cls.safe_float(
                        low_series.min()
                    )

        except Exception:
            pass

        # --------------------------------------------------
        # 5. Financial statements
        # --------------------------------------------------

        income_stmt = None
        balance_sheet_stmt = None
        cashflow_stmt = None

        try:
            income_stmt = ticker.income_stmt
        except Exception as e:
            print(
                f"Income statement unavailable for "
                f"{symbol}: {e}"
            )

        try:
            balance_sheet_stmt = ticker.balance_sheet
        except Exception as e:
            print(
                f"Balance sheet unavailable for "
                f"{symbol}: {e}"
            )

        try:
            cashflow_stmt = ticker.cashflow
        except Exception as e:
            print(
                f"Cash flow unavailable for "
                f"{symbol}: {e}"
            )

        # --------------------------------------------------
        # 6. Extract Income Statement values
        # --------------------------------------------------

        revenue = cls.get_statement_value(
            income_stmt,
            [
                "Total Revenue",
                "Operating Revenue"
            ]
        )

        gross_profit = cls.get_statement_value(
            income_stmt,
            [
                "Gross Profit"
            ]
        )

        operating_income = cls.get_statement_value(
            income_stmt,
            [
                "Operating Income",
                "EBIT"
            ]
        )

        net_income = cls.get_statement_value(
            income_stmt,
            [
                "Net Income",
                "Net Income Common Stockholders"
            ]
        )

        ebitda = cls.get_statement_value(
            income_stmt,
            [
                "EBITDA",
                "Normalized EBITDA"
            ]
        )

        # --------------------------------------------------
        # 7. Extract Balance Sheet values
        # --------------------------------------------------

        total_cash = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Cash Cash Equivalents And Short Term Investments",
                "Cash And Cash Equivalents",
                "Cash Financial"
            ]
        )

        total_debt = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Total Debt",
                "Long Term Debt",
                "Current Debt And Capital Lease Obligation"
            ]
        )

        total_assets = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Total Assets"
            ]
        )

        stockholders_equity = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Stockholders Equity",
                "Total Equity Gross Minority Interest"
            ]
        )

        current_assets = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Current Assets",
                "Total Current Assets"
            ]
        )

        current_liabilities = cls.get_statement_value(
            balance_sheet_stmt,
            [
                "Current Liabilities",
                "Total Current Liabilities"
            ]
        )

        # --------------------------------------------------
        # 8. Extract Cash Flow values
        # --------------------------------------------------

        operating_cash_flow = cls.get_statement_value(
            cashflow_stmt,
            [
                "Operating Cash Flow",
                "Total Cash From Operating Activities"
            ]
        )

        free_cash_flow = cls.get_statement_value(
            cashflow_stmt,
            [
                "Free Cash Flow"
            ]
        )

        capital_expenditure = cls.get_statement_value(
            cashflow_stmt,
            [
                "Capital Expenditure",
                "Capital Expenditures"
            ]
        )

        # Calculate FCF if Yahoo does not provide it

        if (
            free_cash_flow is None
            and operating_cash_flow is not None
            and capital_expenditure is not None
        ):
            free_cash_flow = (
                operating_cash_flow
                + capital_expenditure
            )

        # --------------------------------------------------
        # 9. Market price
        # --------------------------------------------------

        current_price = (
            cls.safe_float(
                fast_info.get("lastPrice")
            )
            or cls.safe_float(
                fast_info.get("last_price")
            )
            or cls.safe_float(
                info.get("currentPrice")
            )
            or cls.safe_float(
                info.get("regularMarketPrice")
            )
            or history_price
        )

        fifty_two_week_high = (
            cls.safe_float(
                fast_info.get("yearHigh")
            )
            or cls.safe_float(
                fast_info.get("year_high")
            )
            or cls.safe_float(
                info.get("fiftyTwoWeekHigh")
            )
            or history_high
        )

        fifty_two_week_low = (
            cls.safe_float(
                fast_info.get("yearLow")
            )
            or cls.safe_float(
                fast_info.get("year_low")
            )
            or cls.safe_float(
                info.get("fiftyTwoWeekLow")
            )
            or history_low
        )

        market_cap = (
            cls.safe_float(
                fast_info.get("marketCap")
            )
            or cls.safe_float(
                fast_info.get("market_cap")
            )
            or cls.safe_float(
                info.get("marketCap")
            )
        )

        shares_outstanding = (
            cls.safe_float(
                fast_info.get("shares")
            )
            or cls.safe_float(
                info.get("sharesOutstanding")
            )
        )

        # --------------------------------------------------
        # 10. Calculated financial ratios
        # --------------------------------------------------

        gross_margin = cls.safe_divide(
            gross_profit,
            revenue
        )

        operating_margin = cls.safe_divide(
            operating_income,
            revenue
        )

        profit_margin = cls.safe_divide(
            net_income,
            revenue
        )

        roe = cls.safe_divide(
            net_income,
            stockholders_equity
        )

        roa = cls.safe_divide(
            net_income,
            total_assets
        )

        current_ratio = cls.safe_divide(
            current_assets,
            current_liabilities
        )

        debt_to_equity = cls.safe_divide(
            total_debt,
            stockholders_equity
        )

        if debt_to_equity is not None:
            debt_to_equity *= 100

        fcf_margin = cls.safe_divide(
            free_cash_flow,
            revenue
        )

        net_debt = None

        if (
            total_debt is not None
            and total_cash is not None
        ):
            net_debt = total_debt - total_cash

        # --------------------------------------------------
        # 11. Profile
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
        # 12. Price statistics
        # --------------------------------------------------

        price_stats = {

            "current_price": current_price,

            "currency": profile["currency"],

            "market_cap": market_cap,

            "enterprise_value": info.get(
                "enterpriseValue"
            ),

            "fifty_two_week_high": (
                fifty_two_week_high
            ),

            "fifty_two_week_low": (
                fifty_two_week_low
            ),

            "fifty_day_average": (
                info.get("fiftyDayAverage")
            ),

            "two_hundred_day_average": (
                info.get("twoHundredDayAverage")
            ),

            "beta": info.get("beta"),

            "shares_outstanding": (
                shares_outstanding
            ),

            "float_shares": info.get(
                "floatShares"
            ),

            "short_ratio": info.get(
                "shortRatio"
            )
        }

        # --------------------------------------------------
        # 13. Valuation
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
        # 14. Profitability
        # --------------------------------------------------

        profitability = {

            "revenue_ttm": (
                revenue
                or info.get("totalRevenue")
            ),

            "revenue_growth_yoy": (
                info.get("revenueGrowth")
            ),

            "gross_margin": (
                gross_margin
                if gross_margin is not None
                else info.get("grossMargins")
            ),

            "operating_margin": (
                operating_margin
                if operating_margin is not None
                else info.get(
                    "operatingMargins"
                )
            ),

            "profit_margin": (
                profit_margin
                if profit_margin is not None
                else info.get(
                    "profitMargins"
                )
            ),

            "ebitda": (
                ebitda
                or info.get("ebitda")
            ),

            "return_on_equity": (
                roe
                if roe is not None
                else info.get(
                    "returnOnEquity"
                )
            ),

            "return_on_assets": (
                roa
                if roa is not None
                else info.get(
                    "returnOnAssets"
                )
            ),

            "earnings_growth_yoy": (
                info.get("earningsGrowth")
            )
        }

        # --------------------------------------------------
        # 15. Balance Sheet
        # --------------------------------------------------

        balance_sheet = {

            "total_cash": (
                total_cash
                or info.get("totalCash")
            ),

            "total_debt": (
                total_debt
                or info.get("totalDebt")
            ),

            "net_debt": net_debt,

            "debt_to_equity": (
                debt_to_equity
                if debt_to_equity is not None
                else info.get(
                    "debtToEquity"
                )
            ),

            "current_ratio": (
                current_ratio
                if current_ratio is not None
                else info.get(
                    "currentRatio"
                )
            ),

            "quick_ratio": info.get(
                "quickRatio"
            )
        }

        # --------------------------------------------------
        # 16. Cash Flow
        # --------------------------------------------------

        cash_flow = {

            "operating_cash_flow": (
                operating_cash_flow
                or info.get(
                    "operatingCashflow"
                )
            ),

            "free_cash_flow": (
                free_cash_flow
                or info.get(
                    "freeCashflow"
                )
            ),

            "fcf_margin": fcf_margin
        }

        # --------------------------------------------------
        # 17. Dividends
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

            "five_year_avg_dividend_yield":
                info.get(
                    "fiveYearAvgDividendYield"
                )
        }

        # --------------------------------------------------
        # 18. Analyst targets
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
        # 19. Historical financial trends
        # --------------------------------------------------

        financial_history = []

        try:

            if (
                income_stmt is not None
                and not income_stmt.empty
            ):

                for column in (
                    income_stmt.columns[:4]
                ):

                    year_str = (
                        str(column.year)
                        if hasattr(column, "year")
                        else str(column)[:10]
                    )

                    financial_history.append({

                        "period": year_str,

                        "revenue":
                            cls.get_statement_value(
                                income_stmt,
                                "Total Revenue",
                                column
                            ),

                        "gross_profit":
                            cls.get_statement_value(
                                income_stmt,
                                "Gross Profit",
                                column
                            ),

                        "operating_income":
                            cls.get_statement_value(
                                income_stmt,
                                "Operating Income",
                                column
                            ),

                        "net_income":
                            cls.get_statement_value(
                                income_stmt,
                                "Net Income",
                                column
                            )
                    })

        except Exception as e:

            print(
                f"Historical extraction error: {e}"
            )

        # --------------------------------------------------
        # 20. Return everything
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

            "history": financial_history
        }
