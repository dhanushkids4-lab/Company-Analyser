import math
import requests
import yfinance as yf

from typing import Dict, Any, Optional


class CompanyDataFetcher:
    """Fetches company market data, financial statements and calculated ratios."""

    # ---------------------------------------------------------
    # Helper functions
    # ---------------------------------------------------------

    @staticmethod
    def _clean_value(value):
        """Convert NaN / invalid numeric values to None."""

        if value is None:
            return None

        try:
            if isinstance(value, float) and math.isnan(value):
                return None
        except Exception:
            pass

        try:
            if str(value).lower() in ("nan", "none", "nat"):
                return None
        except Exception:
            pass

        return value

    @staticmethod
    def _safe_float(value):
        """Safely convert a value to float."""

        value = CompanyDataFetcher._clean_value(value)

        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_divide(numerator, denominator):
        """Safely divide two numbers."""

        numerator = CompanyDataFetcher._safe_float(numerator)
        denominator = CompanyDataFetcher._safe_float(denominator)

        if numerator is None or denominator is None:
            return None

        if denominator == 0:
            return None

        return numerator / denominator

    @staticmethod
    def _safe_dataframe(ticker, attribute):
        """Safely retrieve a yfinance dataframe."""

        try:
            data = getattr(ticker, attribute)

            if data is not None and not data.empty:
                return data

        except Exception as e:
            print(f"Could not load {attribute}: {e}")

        return None

    @staticmethod
    def _latest_statement_value(statement, row_names):
        """
        Get the newest available value from a financial statement.

        row_names can be a string or a list of possible Yahoo row names.
        """

        if statement is None or statement.empty:
            return None

        if isinstance(row_names, str):
            row_names = [row_names]

        for row_name in row_names:

            if row_name not in statement.index:
                continue

            try:
                row = statement.loc[row_name]

                # Columns are normally newest -> oldest
                for value in row.values:

                    value = CompanyDataFetcher._clean_value(value)

                    if value is not None:
                        return CompanyDataFetcher._safe_float(value)

            except Exception:
                continue

        return None

    @staticmethod
    def _statement_value_by_period(statement, row_names, period_index=0):
        """Get a value from a specific statement period."""

        if statement is None or statement.empty:
            return None

        if isinstance(row_names, str):
            row_names = [row_names]

        for row_name in row_names:

            if row_name not in statement.index:
                continue

            try:
                columns = list(statement.columns)

                if period_index >= len(columns):
                    return None

                value = statement.loc[row_name, columns[period_index]]

                return CompanyDataFetcher._safe_float(value)

            except Exception:
                continue

        return None

    @staticmethod
    def _fast_info_to_dict(ticker):
        """Safely convert fast_info to a normal dictionary."""

        try:
            fast_info = ticker.fast_info

            if fast_info is None:
                return {}

            return dict(fast_info)

        except Exception as e:
            print(f"Yahoo Finance fast_info error: {e}")
            return {}

    # ---------------------------------------------------------
    # Ticker search
    # ---------------------------------------------------------

    @staticmethod
    def resolve_ticker(query: str) -> Optional[Dict[str, str]]:
        """
        Resolve company name or ticker to a Yahoo Finance symbol.
        """

        cleaned = query.strip()

        try:

            url = (
                "https://query2.finance.yahoo.com/v1/finance/search"
                f"?q={requests.utils.quote(cleaned)}"
                "&quotesCount=5"
                "&newsCount=0"
            )

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/120 Safari/537.36"
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
                    if q.get("quoteType") in (
                        "EQUITY",
                        "ETF"
                    )
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

        # Direct ticker fallback
        return {
            "symbol": cleaned.upper(),
            "name": cleaned,
            "exchange": "Unknown",
            "quoteType": "EQUITY"
        }

    # ---------------------------------------------------------
    # Main company data fetcher
    # ---------------------------------------------------------

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

        # -----------------------------------------------------
        # INFO
        # -----------------------------------------------------

        try:
            info = ticker.info or {}

        except Exception as e:
            print(
                f"Yahoo Finance info error for "
                f"{symbol}: {e}"
            )
            info = {}

        # -----------------------------------------------------
        # FAST INFO
        # -----------------------------------------------------

        fast_info = cls._fast_info_to_dict(ticker)

        # -----------------------------------------------------
        # FINANCIAL STATEMENTS
        # -----------------------------------------------------

        income_stmt = cls._safe_dataframe(
            ticker,
            "income_stmt"
        )

        balance_sheet_stmt = cls._safe_dataframe(
            ticker,
            "balance_sheet"
        )

        cashflow_stmt = cls._safe_dataframe(
            ticker,
            "cashflow"
        )

        # Try TTM statements if available
        ttm_income_stmt = cls._safe_dataframe(
            ticker,
            "ttm_income_stmt"
        )

        ttm_cashflow_stmt = cls._safe_dataframe(
            ticker,
            "ttm_cashflow"
        )

        # -----------------------------------------------------
        # CURRENT PRICE
        # -----------------------------------------------------

        current_price = (
            fast_info.get("last_price")
            or fast_info.get("lastPrice")
            or info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
            or fast_info.get("previous_close")
            or fast_info.get("previousClose")
        )

        current_price = cls._safe_float(current_price)

        # -----------------------------------------------------
        # MARKET CAP
        # -----------------------------------------------------

        market_cap = (
            fast_info.get("market_cap")
            or fast_info.get("marketCap")
            or info.get("marketCap")
        )

        market_cap = cls._safe_float(market_cap)

        # -----------------------------------------------------
        # SHARES OUTSTANDING
        # -----------------------------------------------------

        shares_outstanding = (
            fast_info.get("shares")
            or fast_info.get("shares_outstanding")
            or info.get("sharesOutstanding")
        )

        shares_outstanding = cls._safe_float(
            shares_outstanding
        )

        # Calculate market cap if necessary
        if (
            market_cap is None
            and current_price is not None
            and shares_outstanding is not None
        ):

            market_cap = (
                current_price
                * shares_outstanding
            )

        # -----------------------------------------------------
        # REVENUE
        # -----------------------------------------------------

        revenue_ttm = (
            info.get("totalRevenue")
        )

        if revenue_ttm is None:

            revenue_ttm = (
                cls._latest_statement_value(
                    ttm_income_stmt,
                    [
                        "Total Revenue",
                        "Operating Revenue"
                    ]
                )
            )

        if revenue_ttm is None:

            revenue_ttm = (
                cls._latest_statement_value(
                    income_stmt,
                    [
                        "Total Revenue",
                        "Operating Revenue"
                    ]
                )
            )

        revenue_ttm = cls._safe_float(
            revenue_ttm
        )

        # -----------------------------------------------------
        # GROSS PROFIT
        # -----------------------------------------------------

        gross_profit = cls._latest_statement_value(
            ttm_income_stmt,
            "Gross Profit"
        )

        if gross_profit is None:

            gross_profit = cls._latest_statement_value(
                income_stmt,
                "Gross Profit"
            )

        # -----------------------------------------------------
        # OPERATING INCOME
        # -----------------------------------------------------

        operating_income = cls._latest_statement_value(
            ttm_income_stmt,
            [
                "Operating Income",
                "EBIT"
            ]
        )

        if operating_income is None:

            operating_income = cls._latest_statement_value(
                income_stmt,
                [
                    "Operating Income",
                    "EBIT"
                ]
            )

        # -----------------------------------------------------
        # NET INCOME
        # -----------------------------------------------------

        net_income = cls._latest_statement_value(
            ttm_income_stmt,
            [
                "Net Income",
                "Net Income Common Stockholders"
            ]
        )

        if net_income is None:

            net_income = cls._latest_statement_value(
                income_stmt,
                [
                    "Net Income",
                    "Net Income Common Stockholders"
                ]
            )

        # -----------------------------------------------------
        # MARGINS
        # -----------------------------------------------------

        gross_margin = (
            info.get("grossMargins")
        )

        if gross_margin is None:

            gross_margin = cls._safe_divide(
                gross_profit,
                revenue_ttm
            )

        operating_margin = (
            info.get("operatingMargins")
        )

        if operating_margin is None:

            operating_margin = cls._safe_divide(
                operating_income,
                revenue_ttm
            )

        profit_margin = (
            info.get("profitMargins")
        )

        if profit_margin is None:

            profit_margin = cls._safe_divide(
                net_income,
                revenue_ttm
            )

        # -----------------------------------------------------
        # EBITDA
        # -----------------------------------------------------

        ebitda = info.get("ebitda")

        if ebitda is None:

            ebitda = cls._latest_statement_value(
                ttm_income_stmt,
                [
                    "EBITDA",
                    "Normalized EBITDA"
                ]
            )

        if ebitda is None:

            ebitda = cls._latest_statement_value(
                income_stmt,
                [
                    "EBITDA",
                    "Normalized EBITDA"
                ]
            )

        ebitda = cls._safe_float(ebitda)

        # -----------------------------------------------------
        # CASH
        # -----------------------------------------------------

        total_cash = info.get("totalCash")

        if total_cash is None:

            total_cash = cls._latest_statement_value(
                balance_sheet_stmt,
                [
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Cash Equivalents",
                    "Cash Financial"
                ]
            )

        total_cash = cls._safe_float(
            total_cash
        )

        # -----------------------------------------------------
        # DEBT
        # -----------------------------------------------------

        total_debt = info.get("totalDebt")

        if total_debt is None:

            total_debt = cls._latest_statement_value(
                balance_sheet_stmt,
                [
                    "Total Debt",
                    "Current Debt And Capital Lease Obligation",
                    "Long Term Debt"
                ]
            )

        total_debt = cls._safe_float(
            total_debt
        )

        # -----------------------------------------------------
        # EQUITY
        # -----------------------------------------------------

        total_equity = cls._latest_statement_value(
            balance_sheet_stmt,
            [
                "Stockholders Equity",
                "Common Stock Equity",
                "Total Equity Gross Minority Interest"
            ]
        )

        # -----------------------------------------------------
        # CURRENT ASSETS / LIABILITIES
        # -----------------------------------------------------

        current_assets = cls._latest_statement_value(
            balance_sheet_stmt,
            "Current Assets"
        )

        current_liabilities = cls._latest_statement_value(
            balance_sheet_stmt,
            "Current Liabilities"
        )

        # -----------------------------------------------------
        # NET DEBT
        # -----------------------------------------------------

        net_debt = None

        if (
            total_debt is not None
            and total_cash is not None
        ):

            net_debt = (
                total_debt
                - total_cash
            )

        # -----------------------------------------------------
        # CURRENT RATIO
        # -----------------------------------------------------

        current_ratio = (
            info.get("currentRatio")
        )

        if current_ratio is None:

            current_ratio = cls._safe_divide(
                current_assets,
                current_liabilities
            )

        # -----------------------------------------------------
        # DEBT TO EQUITY
        # -----------------------------------------------------

        debt_to_equity = (
            info.get("debtToEquity")
        )

        if debt_to_equity is None:

            ratio = cls._safe_divide(
                total_debt,
                total_equity
            )

            if ratio is not None:
                debt_to_equity = ratio * 100

        # -----------------------------------------------------
        # ROE
        # -----------------------------------------------------

        return_on_equity = (
            info.get("returnOnEquity")
        )

        if return_on_equity is None:

            return_on_equity = (
                cls._safe_divide(
                    net_income,
                    total_equity
                )
            )

        # -----------------------------------------------------
        # ROA
        # -----------------------------------------------------

        total_assets = cls._latest_statement_value(
            balance_sheet_stmt,
            "Total Assets"
        )

        return_on_assets = (
            info.get("returnOnAssets")
        )

        if return_on_assets is None:

            return_on_assets = (
                cls._safe_divide(
                    net_income,
                    total_assets
                )
            )

        # -----------------------------------------------------
        # OPERATING CASH FLOW
        # -----------------------------------------------------

        operating_cash_flow = (
            info.get("operatingCashflow")
        )

        if operating_cash_flow is None:

            operating_cash_flow = (
                cls._latest_statement_value(
                    ttm_cashflow_stmt,
                    [
                        "Operating Cash Flow",
                        "Total Cash From Operating Activities"
                    ]
                )
            )

        if operating_cash_flow is None:

            operating_cash_flow = (
                cls._latest_statement_value(
                    cashflow_stmt,
                    [
                        "Operating Cash Flow",
                        "Total Cash From Operating Activities"
                    ]
                )
            )

        operating_cash_flow = cls._safe_float(
            operating_cash_flow
        )

        # -----------------------------------------------------
        # CAPITAL EXPENDITURES
        # -----------------------------------------------------

        capital_expenditure = cls._latest_statement_value(
            ttm_cashflow_stmt,
            [
                "Capital Expenditure",
                "Capital Expenditures"
            ]
        )

        if capital_expenditure is None:

            capital_expenditure = (
                cls._latest_statement_value(
                    cashflow_stmt,
                    [
                        "Capital Expenditure",
                        "Capital Expenditures"
                    ]
                )
            )

        # -----------------------------------------------------
        # FREE CASH FLOW
        # -----------------------------------------------------

        free_cash_flow = (
            info.get("freeCashflow")
        )

        if (
            free_cash_flow is None
            and operating_cash_flow is not None
            and capital_expenditure is not None
        ):

            # Yahoo normally stores CapEx as negative
            free_cash_flow = (
                operating_cash_flow
                + capital_expenditure
            )

        free_cash_flow = cls._safe_float(
            free_cash_flow
        )

        fcf_margin = cls._safe_divide(
            free_cash_flow,
            revenue_ttm
        )

        # -----------------------------------------------------
        # BOOK VALUE PER SHARE
        # -----------------------------------------------------

        book_value = info.get("bookValue")

        if book_value is None:

            book_value = cls._safe_divide(
                total_equity,
                shares_outstanding
            )

        # -----------------------------------------------------
        # EPS
        # -----------------------------------------------------

        trailing_eps = (
            info.get("trailingEps")
        )

        if trailing_eps is None:

            trailing_eps = (
                cls._latest_statement_value(
                    ttm_income_stmt,
                    [
                        "Diluted EPS",
                        "Basic EPS"
                    ]
                )
            )

        if trailing_eps is None:

            trailing_eps = (
                cls._latest_statement_value(
                    income_stmt,
                    [
                        "Diluted EPS",
                        "Basic EPS"
                    ]
                )
            )

        trailing_eps = cls._safe_float(
            trailing_eps
        )

        # -----------------------------------------------------
        # VALUATION FALLBACKS
        # -----------------------------------------------------

        trailing_pe = (
            info.get("trailingPE")
        )

        if trailing_pe is None:

            trailing_pe = cls._safe_divide(
                current_price,
                trailing_eps
            )

        forward_pe = (
            info.get("forwardPE")
        )

        price_to_sales = (
            info.get(
                "priceToSalesTrailing12Months"
            )
        )

        if price_to_sales is None:

            price_to_sales = (
                cls._safe_divide(
                    market_cap,
                    revenue_ttm
                )
            )

        price_to_book = (
            info.get("priceToBook")
        )

        if price_to_book is None:

            price_to_book = (
                cls._safe_divide(
                    current_price,
                    book_value
                )
            )

        # -----------------------------------------------------
        # ENTERPRISE VALUE
        # -----------------------------------------------------

        enterprise_value = (
            info.get("enterpriseValue")
        )

        if (
            enterprise_value is None
            and market_cap is not None
        ):

            enterprise_value = market_cap

            if total_debt is not None:
                enterprise_value += total_debt

            if total_cash is not None:
                enterprise_value -= total_cash

        enterprise_value = cls._safe_float(
            enterprise_value
        )

        ev_to_ebitda = (
            info.get("enterpriseToEbitda")
        )

        if ev_to_ebitda is None:

            ev_to_ebitda = (
                cls._safe_divide(
                    enterprise_value,
                    ebitda
                )
            )

        ev_to_revenue = (
            info.get("enterpriseToRevenue")
        )

        if ev_to_revenue is None:

            ev_to_revenue = (
                cls._safe_divide(
                    enterprise_value,
                    revenue_ttm
                )
            )

        # -----------------------------------------------------
        # REVENUE GROWTH
        # -----------------------------------------------------

        revenue_growth_yoy = (
            info.get("revenueGrowth")
        )

        if (
            revenue_growth_yoy is None
            and income_stmt is not None
            and len(income_stmt.columns) >= 2
        ):

            latest_revenue = (
                cls._statement_value_by_period(
                    income_stmt,
                    [
                        "Total Revenue",
                        "Operating Revenue"
                    ],
                    0
                )
            )

            previous_revenue = (
                cls._statement_value_by_period(
                    income_stmt,
                    [
                        "Total Revenue",
                        "Operating Revenue"
                    ],
                    1
                )
            )

            if (
                latest_revenue is not None
                and previous_revenue is not None
                and previous_revenue != 0
            ):

                revenue_growth_yoy = (
                    latest_revenue
                    / previous_revenue
                    - 1
                )

        # -----------------------------------------------------
        # EARNINGS GROWTH
        # -----------------------------------------------------

        earnings_growth_yoy = (
            info.get("earningsGrowth")
        )

        # -----------------------------------------------------
        # 52 WEEK DATA
        # -----------------------------------------------------

        fifty_two_week_high = (
            fast_info.get("year_high")
            or fast_info.get("yearHigh")
            or info.get("fiftyTwoWeekHigh")
        )

        fifty_two_week_low = (
            fast_info.get("year_low")
            or fast_info.get("yearLow")
            or info.get("fiftyTwoWeekLow")
        )

        fifty_day_average = (
            info.get("fiftyDayAverage")
        )

        two_hundred_day_average = (
            info.get("twoHundredDayAverage")
        )

        # -----------------------------------------------------
        # PRICE HISTORY FALLBACK
        # -----------------------------------------------------

        try:

            history_prices = ticker.history(
                period="1y",
                auto_adjust=False
            )

            if (
                history_prices is not None
                and not history_prices.empty
            ):

                if fifty_two_week_high is None:

                    fifty_two_week_high = cls._safe_float(
                        history_prices["High"].max()
                    )

                if fifty_two_week_low is None:

                    fifty_two_week_low = cls._safe_float(
                        history_prices["Low"].min()
                    )

                if fifty_day_average is None:

                    fifty_day_average = cls._safe_float(
                        history_prices["Close"]
                        .tail(50)
                        .mean()
                    )

                if two_hundred_day_average is None:

                    two_hundred_day_average = (
                        cls._safe_float(
                            history_prices["Close"]
                            .tail(200)
                            .mean()
                        )
                    )

        except Exception as e:
            print(
                f"Price history error for "
                f"{symbol}: {e}"
            )

        # -----------------------------------------------------
        # ANALYST TARGETS
        # -----------------------------------------------------

        analyst_price_targets = {}

        try:

            targets_data = (
                ticker.analyst_price_targets
            )

            if targets_data:

                analyst_price_targets = (
                    dict(targets_data)
                )

        except Exception as e:
            print(
                f"Analyst targets error for "
                f"{symbol}: {e}"
            )

        target_mean_price = (
            info.get("targetMeanPrice")
            or analyst_price_targets.get("mean")
        )

        target_high_price = (
            info.get("targetHighPrice")
            or analyst_price_targets.get("high")
        )

        target_low_price = (
            info.get("targetLowPrice")
            or analyst_price_targets.get("low")
        )

        target_median_price = (
            info.get("targetMedianPrice")
            or analyst_price_targets.get("median")
        )

        # -----------------------------------------------------
        # PROFILE
        # -----------------------------------------------------

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
            "full_time_employees": (
                info.get(
                    "fullTimeEmployees"
                )
            ),
            "currency": (
                fast_info.get("currency")
                or info.get(
                    "currency",
                    "USD"
                )
            ),
            "exchange": (
                info.get("exchange")
                or resolved.get("exchange")
                or "N/A"
            ),
            "summary": (
                info.get(
                    "longBusinessSummary",
                    ""
                )
            )
        }

        # -----------------------------------------------------
        # PRICE STATS
        # -----------------------------------------------------

        price_stats = {
            "current_price": current_price,
            "currency": profile["currency"],
            "market_cap": market_cap,
            "enterprise_value": enterprise_value,
            "fifty_two_week_high": (
                cls._safe_float(
                    fifty_two_week_high
                )
            ),
            "fifty_two_week_low": (
                cls._safe_float(
                    fifty_two_week_low
                )
            ),
            "fifty_day_average": (
                cls._safe_float(
                    fifty_day_average
                )
            ),
            "two_hundred_day_average": (
                cls._safe_float(
                    two_hundred_day_average
                )
            ),
            "beta": info.get("beta"),
            "shares_outstanding": (
                shares_outstanding
            ),
            "float_shares": (
                info.get("floatShares")
            ),
            "short_ratio": (
                info.get("shortRatio")
            )
        }

        # -----------------------------------------------------
        # VALUATION
        # -----------------------------------------------------

        valuation = {
            "trailing_pe": (
                cls._safe_float(
                    trailing_pe
                )
            ),
            "forward_pe": (
                cls._safe_float(
                    forward_pe
                )
            ),
            "peg_ratio": (
                cls._safe_float(
                    info.get("pegRatio")
                    or info.get(
                        "trailingPegRatio"
                    )
                )
            ),
            "price_to_book": (
                cls._safe_float(
                    price_to_book
                )
            ),
            "price_to_sales": (
                cls._safe_float(
                    price_to_sales
                )
            ),
            "ev_to_ebitda": (
                cls._safe_float(
                    ev_to_ebitda
                )
            ),
            "ev_to_revenue": (
                cls._safe_float(
                    ev_to_revenue
                )
            ),
            "book_value": (
                cls._safe_float(
                    book_value
                )
            )
        }

        # -----------------------------------------------------
        # PROFITABILITY
        # -----------------------------------------------------

        profitability = {
            "revenue_ttm": (
                revenue_ttm
            ),
            "revenue_growth_yoy": (
                cls._safe_float(
                    revenue_growth_yoy
                )
            ),
            "gross_margin": (
                cls._safe_float(
                    gross_margin
                )
            ),
            "operating_margin": (
                cls._safe_float(
                    operating_margin
                )
            ),
            "profit_margin": (
                cls._safe_float(
                    profit_margin
                )
            ),
            "ebitda": (
                ebitda
            ),
            "return_on_equity": (
                cls._safe_float(
                    return_on_equity
                )
            ),
            "return_on_assets": (
                cls._safe_float(
                    return_on_assets
                )
            ),
            "earnings_growth_yoy": (
                cls._safe_float(
                    earnings_growth_yoy
                )
            )
        }

        # -----------------------------------------------------
        # BALANCE SHEET
        # -----------------------------------------------------

        balance_sheet = {
            "total_cash": total_cash,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "debt_to_equity": (
                cls._safe_float(
                    debt_to_equity
                )
            ),
            "current_ratio": (
                cls._safe_float(
                    current_ratio
                )
            ),
            "quick_ratio": (
                cls._safe_float(
                    info.get("quickRatio")
                )
            )
        }

        # -----------------------------------------------------
        # CASH FLOW
        # -----------------------------------------------------

        cash_flow = {
            "operating_cash_flow": (
                operating_cash_flow
            ),
            "free_cash_flow": (
                free_cash_flow
            ),
            "fcf_margin": (
                cls._safe_float(
                    fcf_margin
                )
            )
        }

        # -----------------------------------------------------
        # DIVIDENDS
        # -----------------------------------------------------

        dividends = {
            "dividend_rate": (
                info.get("dividendRate")
            ),
            "dividend_yield": (
                info.get("dividendYield")
            ),
            "payout_ratio": (
                info.get("payoutRatio")
            ),
            "five_year_avg_dividend_yield": (
                info.get(
                    "fiveYearAvgDividendYield"
                )
            )
        }

        # -----------------------------------------------------
        # ANALYST TARGETS
        # -----------------------------------------------------

        analyst_targets = {
            "target_mean_price": (
                cls._safe_float(
                    target_mean_price
                )
            ),
            "target_high_price": (
                cls._safe_float(
                    target_high_price
                )
            ),
            "target_low_price": (
                cls._safe_float(
                    target_low_price
                )
            ),
            "target_median_price": (
                cls._safe_float(
                    target_median_price
                )
            ),
            "recommendation_key": (
                info.get(
                    "recommendationKey"
                )
            ),
            "number_of_analysts": (
                info.get(
                    "numberOfAnalystOpinions"
                )
            )
        }

        # -----------------------------------------------------
        # HISTORICAL FINANCIAL DATA
        # -----------------------------------------------------

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

                    rev = (
                        income_stmt.loc[
                            "Total Revenue",
                            col
                        ]
                        if "Total Revenue"
                        in income_stmt.index
                        else None
                    )

                    gp = (
                        income_stmt.loc[
                            "Gross Profit",
                            col
                        ]
                        if "Gross Profit"
                        in income_stmt.index
                        else None
                    )

                    op = (
                        income_stmt.loc[
                            "Operating Income",
                            col
                        ]
                        if "Operating Income"
                        in income_stmt.index
                        else None
                    )

                    ni = (
                        income_stmt.loc[
                            "Net Income",
                            col
                        ]
                        if "Net Income"
                        in income_stmt.index
                        else None
                    )

                    history.append({
                        "period": year_str,
                        "revenue": (
                            cls._safe_float(
                                rev
                            )
                        ),
                        "gross_profit": (
                            cls._safe_float(
                                gp
                            )
                        ),
                        "operating_income": (
                            cls._safe_float(
                                op
                            )
                        ),
                        "net_income": (
                            cls._safe_float(
                                ni
                            )
                        )
                    })

        except Exception as e:
            print(
                f"Historical financial data "
                f"error: {e}"
            )

        # -----------------------------------------------------
        # FINAL RESPONSE
        # -----------------------------------------------------

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
