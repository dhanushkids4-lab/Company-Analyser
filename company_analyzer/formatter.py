import json
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich import box


def _fmt_curr(val: Optional[float], currency: str = "$", decimals: int = 2) -> str:
    if val is None or str(val).lower() == 'nan':
        return "N/A"
    return f"{currency}{val:,.{decimals}f}"


def _fmt_large_num(val: Optional[float], currency: str = "$") -> str:
    if val is None or str(val).lower() == 'nan':
        return "N/A"
    abs_val = abs(val)
    sign = "-" if val < 0 else ""
    if abs_val >= 1e12:
        return f"{sign}{currency}{abs_val / 1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"{sign}{currency}{abs_val / 1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"{sign}{currency}{abs_val / 1e6:.2f}M"
    elif abs_val >= 1e3:
        return f"{sign}{currency}{abs_val / 1e3:.2f}K"
    return f"{sign}{currency}{abs_val:.2f}"


def _fmt_pct(val: Optional[float], is_already_percent: bool = False) -> str:
    if val is None or str(val).lower() == 'nan':
        return "N/A"
    if is_already_percent:
        return f"{val:.2f}%"
    return f"{val * 100:.2f}%"


def _fmt_mult(val: Optional[float]) -> str:
    if val is None or str(val).lower() == 'nan':
        return "N/A"
    return f"{val:.2f}x"


class ReportFormatter:
    """Formats company analysis into Rich terminal display, Markdown, JSON, and HTML."""

    @classmethod
    def display_rich(cls, company_data: Dict[str, Any], score_data: Dict[str, Any], memo: Optional[str] = None):
        console = Console()
        profile = company_data.get("profile", {})
        price = company_data.get("price_stats", {})
        val = company_data.get("valuation", {})
        prof = company_data.get("profitability", {})
        bs = company_data.get("balance_sheet", {})
        cf = company_data.get("cash_flow", {})
        divs = company_data.get("dividends", {})
        targets = company_data.get("analyst_targets", {})
        history = company_data.get("history", [])

        curr_symbol = "$" if profile.get("currency") == "USD" else f"{profile.get('currency')} "

        # Header Title Panel
        grade = score_data.get("grade", "N/A")
        score = score_data.get("overall_score", 0)
        grade_color = "green" if "A" in grade else ("cyan" if "B" in grade else ("yellow" if "C" in grade else "red"))

        header_text = Text()
        header_text.append(f"{profile.get('name')} ", style="bold white")
        header_text.append(f"[{profile.get('symbol')}]", style="bold cyan")
        header_text.append(f"  •  {profile.get('sector')} | {profile.get('industry')}\n", style="dim")
        header_text.append(f"Price: ", style="bold")
        header_text.append(f"{_fmt_curr(price.get('current_price'), curr_symbol)}", style="bold green")
        header_text.append(f"  |  Market Cap: {_fmt_large_num(price.get('market_cap'), curr_symbol)}")
        header_text.append(f"  |  Health Score: ", style="bold")
        header_text.append(f"{score}/100 ({grade})", style=f"bold {grade_color}")

        console.print(Panel(header_text, border_style="cyan", title="🏢 Company Analysis Dossier", title_align="left"))

        # 2 Column Key Metrics
        # Left: Valuation & Trading
        val_table = Table(title="📊 Valuation & Trading", box=box.ROUNDED, expand=True)
        val_table.add_column("Metric", style="dim")
        val_table.add_column("Value", justify="right", style="bold")

        val_table.add_row("Trailing P/E", _fmt_mult(val.get("trailing_pe")))
        val_table.add_row("Forward P/E", _fmt_mult(val.get("forward_pe")))
        val_table.add_row("PEG Ratio", f"{val.get('peg_ratio'):.2f}" if val.get("peg_ratio") else "N/A")
        val_table.add_row("Price / Sales (P/S)", _fmt_mult(val.get("price_to_sales")))
        val_table.add_row("Price / Book (P/B)", _fmt_mult(val.get("price_to_book")))
        val_table.add_row("EV / EBITDA", _fmt_mult(val.get("ev_to_ebitda")))
        val_table.add_row("Enterprise Value", _fmt_large_num(price.get("enterprise_value"), curr_symbol))
        val_table.add_row("52-Week Range", f"{_fmt_curr(price.get('fifty_two_week_low'), curr_symbol)} - {_fmt_curr(price.get('fifty_two_week_high'), curr_symbol)}")
        val_table.add_row("Beta (Volatility)", f"{price.get('beta'):.2f}" if price.get("beta") else "N/A")
        val_table.add_row("Dividend Yield", _fmt_pct(divs.get("dividend_yield"), is_already_percent=True))

        # Right: Financial Performance & Balance Sheet
        fin_table = Table(title="💰 Financials & Solvency", box=box.ROUNDED, expand=True)
        fin_table.add_column("Metric", style="dim")
        fin_table.add_column("Value", justify="right", style="bold")

        fin_table.add_row("Revenue (TTM)", _fmt_large_num(prof.get("revenue_ttm"), curr_symbol))
        fin_table.add_row("Revenue Growth (YoY)", _fmt_pct(prof.get("revenue_growth_yoy")))
        fin_table.add_row("Gross Margin", _fmt_pct(prof.get("gross_margin")))
        fin_table.add_row("Operating Margin", _fmt_pct(prof.get("operating_margin")))
        fin_table.add_row("Net Profit Margin", _fmt_pct(prof.get("profit_margin")))
        fin_table.add_row("Return on Equity (ROE)", _fmt_pct(prof.get("return_on_equity")))
        fin_table.add_row("Free Cash Flow", _fmt_large_num(cf.get("free_cash_flow"), curr_symbol))
        fin_table.add_row("Total Cash", _fmt_large_num(bs.get("total_cash"), curr_symbol))
        fin_table.add_row("Total Debt", _fmt_large_num(bs.get("total_debt"), curr_symbol))
        fin_table.add_row("Debt to Equity", f"{bs.get('debt_to_equity'):.1f}%" if bs.get("debt_to_equity") is not None else "N/A")
        fin_table.add_row("Current Ratio", f"{bs.get('current_ratio'):.2f}" if bs.get("current_ratio") is not None else "N/A")

        console.print(Columns([val_table, fin_table]))

        # Historical Trend Table if available
        if history:
            hist_table = Table(title="📈 Multi-Year Financial Performance History", box=box.ROUNDED, expand=True)
            hist_table.add_column("Period", style="bold")
            hist_table.add_column("Revenue", justify="right")
            hist_table.add_column("Gross Profit", justify="right")
            hist_table.add_column("Operating Income", justify="right")
            hist_table.add_column("Net Income", justify="right")

            for row in history:
                hist_table.add_row(
                    str(row.get("period")),
                    _fmt_large_num(row.get("revenue"), curr_symbol),
                    _fmt_large_num(row.get("gross_profit"), curr_symbol),
                    _fmt_large_num(row.get("operating_income"), curr_symbol),
                    _fmt_large_num(row.get("net_income"), curr_symbol)
                )
            console.print(hist_table)

        # Analyst Consensus Panel
        rec = str(targets.get("recommendation_key", "N/A")).upper().replace("_", " ")
        mean_tgt = _fmt_curr(targets.get("target_mean_price"), curr_symbol)
        high_tgt = _fmt_curr(targets.get("target_high_price"), curr_symbol)
        low_tgt = _fmt_curr(targets.get("target_low_price"), curr_symbol)
        num_analysts = targets.get("number_of_analysts") or "N/A"

        analyst_text = f"[bold]Consensus Rating:[/bold] [green]{rec}[/green] ({num_analysts} Analysts)  |  " \
                       f"[bold]Target Mean:[/bold] {mean_tgt}  |  " \
                       f"[bold]Target Range:[/bold] {low_tgt} - {high_tgt}"
        console.print(Panel(analyst_text, title="🎯 Wall Street Price Targets & Consensus", border_style="magenta"))

        # Strengths & Risks Cards
        str_text = "\n".join([f"  ✅ {s}" for s in score_data.get("strengths", [])]) or "  No major flags."
        risk_text = "\n".join([f"  ⚠️  {r}" for r in score_data.get("risks", [])]) or "  No major risks flagged."

        str_panel = Panel(str_text, title="💪 Key Strengths & Competitive Edges", border_style="green")
        risk_panel = Panel(risk_text, title="⚠️ Key Risks & Solvency Watchpoints", border_style="red")
        console.print(Columns([str_panel, risk_panel]))

        # Executive Memo
        if memo:
            console.print(Panel(memo, title="🧠 Agent Strategic & Investment Synthesis", border_style="blue"))

    @classmethod
    def to_markdown(cls, company_data: Dict[str, Any], score_data: Dict[str, Any], memo: Optional[str] = None) -> str:
        profile = company_data.get("profile", {})
        price = company_data.get("price_stats", {})
        val = company_data.get("valuation", {})
        prof = company_data.get("profitability", {})
        bs = company_data.get("balance_sheet", {})
        cf = company_data.get("cash_flow", {})
        divs = company_data.get("dividends", {})
        targets = company_data.get("analyst_targets", {})
        history = company_data.get("history", [])

        curr_symbol = "$" if profile.get("currency") == "USD" else f"{profile.get('currency')} "

        md = []
        md.append(f"# Company Analysis Report: {profile.get('name')} ({profile.get('symbol')})\n")
        md.append(f"**Sector:** {profile.get('sector')} | **Industry:** {profile.get('industry')} | **Country:** {profile.get('country')}")
        md.append(f"**Health Score:** {score_data.get('overall_score')}/100 (**Grade: {score_data.get('grade')}**)")
        md.append(f"**Current Price:** {_fmt_curr(price.get('current_price'), curr_symbol)} | **Market Cap:** {_fmt_large_num(price.get('market_cap'), curr_symbol)}\n")

        md.append("## 📊 Key Valuation & Market Multiples\n")
        md.append("| Metric | Value | Metric | Value |")
        md.append("|---|---|---|---|")
        md.append(f"| Trailing P/E | {_fmt_mult(val.get('trailing_pe'))} | Forward P/E | {_fmt_mult(val.get('forward_pe'))} |")
        md.append(f"| PEG Ratio | {val.get('peg_ratio') or 'N/A'} | Price / Sales | {_fmt_mult(val.get('price_to_sales'))} |")
        md.append(f"| Price / Book | {_fmt_mult(val.get('price_to_book'))} | EV / EBITDA | {_fmt_mult(val.get('ev_to_ebitda'))} |")
        md.append(f"| Enterprise Value | {_fmt_large_num(price.get('enterprise_value'), curr_symbol)} | 52W High / Low | {_fmt_curr(price.get('fifty_two_week_high'), curr_symbol)} / {_fmt_curr(price.get('fifty_two_week_low'), curr_symbol)} |")
        md.append(f"| Beta | {price.get('beta') or 'N/A'} | Dividend Yield | {_fmt_pct(divs.get('dividend_yield'), is_already_percent=True)} |\n")

        md.append("## 💰 Financial Performance & Solvency\n")
        md.append("| Financial Metric | Value | Balance Sheet Metric | Value |")
        md.append("|---|---|---|---|")
        md.append(f"| Revenue (TTM) | {_fmt_large_num(prof.get('revenue_ttm'), curr_symbol)} | Total Cash | {_fmt_large_num(bs.get('total_cash'), curr_symbol)} |")
        md.append(f"| Revenue Growth (YoY) | {_fmt_pct(prof.get('revenue_growth_yoy'))} | Total Debt | {_fmt_large_num(bs.get('total_debt'), curr_symbol)} |")
        md.append(f"| Gross Margin | {_fmt_pct(prof.get('gross_margin'))} | Net Debt | {_fmt_large_num(bs.get('net_debt'), curr_symbol)} |")
        md.append(f"| Operating Margin | {_fmt_pct(prof.get('operating_margin'))} | Debt / Equity | {bs.get('debt_to_equity') or 'N/A'}% |")
        md.append(f"| Net Profit Margin | {_fmt_pct(prof.get('profit_margin'))} | Current Ratio | {bs.get('current_ratio') or 'N/A'} |")
        md.append(f"| Return on Equity (ROE) | {_fmt_pct(prof.get('return_on_equity'))} | Free Cash Flow | {_fmt_large_num(cf.get('free_cash_flow'), curr_symbol)} |\n")

        if history:
            md.append("## 📈 Historical Financial Performance\n")
            md.append("| Period | Revenue | Gross Profit | Operating Income | Net Income |")
            md.append("|---|---|---|---|---|")
            for h in history:
                md.append(f"| {h.get('period')} | {_fmt_large_num(h.get('revenue'), curr_symbol)} | {_fmt_large_num(h.get('gross_profit'), curr_symbol)} | {_fmt_large_num(h.get('operating_income'), curr_symbol)} | {_fmt_large_num(h.get('net_income'), curr_symbol)} |")
            md.append("\n")

        md.append("## 🎯 Analyst Targets & Wall Street Consensus\n")
        rec = str(targets.get("recommendation_key", "N/A")).upper().replace("_", " ")
        md.append(f"- **Consensus Recommendation:** `{rec}` ({targets.get('number_of_analysts') or 'N/A'} Analysts)")
        md.append(f"- **Mean Price Target:** {_fmt_curr(targets.get('target_mean_price'), curr_symbol)}")
        md.append(f"- **Target Range:** Low: {_fmt_curr(targets.get('target_low_price'), curr_symbol)} — High: {_fmt_curr(targets.get('target_high_price'), curr_symbol)}\n")

        md.append("## ⚖️ Key Strengths & Risk Factors\n")
        md.append("### Strengths")
        for s in score_data.get("strengths", []):
            md.append(f"- ✅ {s}")
        md.append("\n### Risks")
        for r in score_data.get("risks", []):
            md.append(f"- ⚠️ {r}")
        md.append("\n")

        if memo:
            md.append("## 🧠 Strategic Synthesis Memo\n")
            md.append(memo)

        return "\n".join(md)

    @classmethod
    def to_json(cls, company_data: Dict[str, Any], score_data: Dict[str, Any], memo: Optional[str] = None) -> str:
        payload = {
            "company_data": company_data,
            "scoring": score_data,
            "memo": memo
        }
        return json.dumps(payload, indent=2)

    @classmethod
    def to_html(cls, company_data: Dict[str, Any], score_data: Dict[str, Any], memo: Optional[str] = None) -> str:
        profile = company_data.get("profile", {})
        price = company_data.get("price_stats", {})
        val = company_data.get("valuation", {})
        prof = company_data.get("profitability", {})
        bs = company_data.get("balance_sheet", {})
        cf = company_data.get("cash_flow", {})
        divs = company_data.get("dividends", {})
        targets = company_data.get("analyst_targets", {})
        history = company_data.get("history", [])

        curr_symbol = "$" if profile.get("currency") == "USD" else f"{profile.get('currency')} "
        grade = score_data.get("grade", "N/A")
        score = score_data.get("overall_score", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{profile.get('name')} ({profile.get('symbol')}) - Company Analysis</title>
<style>
  :root {{
    --bg: #0d1117;
    --card-bg: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --heading: #f0f6fc;
    --accent: #58a6ff;
    --green: #3fb950;
    --red: #f85149;
    --yellow: #d29922;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg);
    color: var(--text);
    margin: 0;
    padding: 30px 20px;
  }}
  .container {{ max-width: 1050px; margin: auto; }}
  .header {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }}
  .header h1 {{ margin: 0 0 6px 0; color: var(--heading); font-size: 26px; }}
  .header .meta {{ color: #8b949e; font-size: 14px; }}
  .score-badge {{
    background: #21262d;
    border: 2px solid var(--accent);
    border-radius: 10px;
    padding: 12px 20px;
    text-align: center;
  }}
  .score-badge .score {{ font-size: 28px; font-weight: bold; color: var(--accent); }}
  .score-badge .grade {{ font-size: 14px; color: #8b949e; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
    margin-bottom: 24px;
  }}
  .card {{
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
  }}
  .card h2 {{ margin-top: 0; font-size: 18px; color: var(--heading); border-bottom: 1px solid var(--border); padding-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  td, th {{ padding: 8px 4px; text-align: left; font-size: 14px; }}
  td:last-child, th:last-child {{ text-align: right; }}
  tr:not(:last-child) td {{ border-bottom: 1px solid #21262d; }}
  .label {{ color: #8b949e; }}
  .val {{ font-weight: 600; color: var(--heading); }}
  .list-item {{ padding: 6px 0; font-size: 14px; display: flex; align-items: flex-start; gap: 8px; }}
  .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }}
  .tag-green {{ background: rgba(63, 185, 80, 0.2); color: var(--green); }}
  .memo {{ line-height: 1.6; white-space: pre-wrap; font-size: 14px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div>
      <h1>{profile.get('name')} <span style="color:var(--accent)">({profile.get('symbol')})</span></h1>
      <div class="meta">{profile.get('sector')} • {profile.get('industry')} • {profile.get('exchange')}</div>
      <div style="margin-top: 10px; font-size: 20px; font-weight: bold; color: var(--green)">
        {_fmt_curr(price.get('current_price'), curr_symbol)}
        <span style="font-size: 14px; color: #8b949e; font-weight: normal; margin-left: 10px;">Market Cap: {_fmt_large_num(price.get('market_cap'), curr_symbol)}</span>
      </div>
    </div>
    <div class="score-badge">
      <div class="score">{score}/100</div>
      <div class="grade">Grade: {grade}</div>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2>📊 Valuation Multiples</h2>
      <table>
        <tr><td class="label">Trailing P/E</td><td class="val">{_fmt_mult(val.get('trailing_pe'))}</td></tr>
        <tr><td class="label">Forward P/E</td><td class="val">{_fmt_mult(val.get('forward_pe'))}</td></tr>
        <tr><td class="label">PEG Ratio</td><td class="val">{val.get('peg_ratio') or 'N/A'}</td></tr>
        <tr><td class="label">Price / Sales</td><td class="val">{_fmt_mult(val.get('price_to_sales'))}</td></tr>
        <tr><td class="label">Price / Book</td><td class="val">{_fmt_mult(val.get('price_to_book'))}</td></tr>
        <tr><td class="label">EV / EBITDA</td><td class="val">{_fmt_mult(val.get('ev_to_ebitda'))}</td></tr>
        <tr><td class="label">Enterprise Value</td><td class="val">{_fmt_large_num(price.get('enterprise_value'), curr_symbol)}</td></tr>
        <tr><td class="label">52W Range</td><td class="val">{_fmt_curr(price.get('fifty_two_week_low'), curr_symbol)} - {_fmt_curr(price.get('fifty_two_week_high'), curr_symbol)}</td></tr>
      </table>
    </div>

    <div class="card">
      <h2>💰 Financials & Solvency</h2>
      <table>
        <tr><td class="label">Revenue (TTM)</td><td class="val">{_fmt_large_num(prof.get('revenue_ttm'), curr_symbol)}</td></tr>
        <tr><td class="label">Revenue Growth (YoY)</td><td class="val">{_fmt_pct(prof.get('revenue_growth_yoy'))}</td></tr>
        <tr><td class="label">Gross Margin</td><td class="val">{_fmt_pct(prof.get('gross_margin'))}</td></tr>
        <tr><td class="label">Operating Margin</td><td class="val">{_fmt_pct(prof.get('operating_margin'))}</td></tr>
        <tr><td class="label">Net Profit Margin</td><td class="val">{_fmt_pct(prof.get('profit_margin'))}</td></tr>
        <tr><td class="label">Return on Equity (ROE)</td><td class="val">{_fmt_pct(prof.get('return_on_equity'))}</td></tr>
        <tr><td class="label">Free Cash Flow</td><td class="val">{_fmt_large_num(cf.get('free_cash_flow'), curr_symbol)}</td></tr>
        <tr><td class="label">Total Debt / Cash</td><td class="val">{_fmt_large_num(bs.get('total_debt'), curr_symbol)} / {_fmt_large_num(bs.get('total_cash'), curr_symbol)}</td></tr>
      </table>
    </div>
  </div>

  <div class="grid">
    <div class="card">
      <h2 style="color:var(--green)">💪 Key Strengths</h2>
      {''.join([f'<div class="list-item"><span>✅</span> <span>{s}</span></div>' for s in score_data.get('strengths', [])])}
    </div>
    <div class="card">
      <h2 style="color:var(--red)">⚠️ Key Risks & Watchpoints</h2>
      {''.join([f'<div class="list-item"><span>⚠️</span> <span>{r}</span></div>' for r in score_data.get('risks', [])])}
    </div>
  </div>

  {'<div class="card"><h2>🧠 Strategic Synthesis Memo</h2><div class="memo">' + (memo or "") + '</div></div>' if memo else ''}
</div>
</body>
</html>
"""
        return html
