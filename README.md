# 🏢 Autonomous Company & Financial Analysis Agent & Web Platform

An intelligent, multi-market financial research platform and AI agent that extracts deep company fundamentals, computes solvency and valuation scores, detects risk factors, and synthesizes Wall Street-grade investment memos.

---

## ⚡ Key Capabilities

- **Global Market Coverage**: Supports US (`AAPL`, `MSFT`, `NVDA`), Indian (`RELIANCE.NS`, `TCS.NS`), European, and international exchanges.
- **Interactive Web App**: Modern financial terminal web dashboard with interactive multi-year Chart.js visualizations, health score gauges, and a real-time conversational AI analyst Q&A tab.
- **Smart Ticker Resolution**: Type either a ticker (`TSLA`) or a company name (`"Microsoft"`, `"Tata Motors"`).
- **Core Financial & Valuation Extraction**:
  - **Valuation Multiples**: Trailing P/E, Forward P/E, PEG Ratio, Price-to-Sales (P/S), Price-to-Book (P/B), EV/EBITDA, EV/Revenue.
  - **Profitability & Returns**: Revenue TTM, YoY Growth, Gross/Operating/Net Margins, Return on Equity (ROE), Return on Assets (ROA).
  - **Solvency & Balance Sheet**: Total Cash, Total Debt, Net Debt, Debt-to-Equity, Current Ratio, Quick Ratio.
  - **Cash Flow**: Operating Cash Flow, Free Cash Flow, FCF Margin.
  - **Consensus & Targets**: Wall Street consensus (Buy/Hold/Sell), Mean/High/Low price targets, number of analysts.
  - **Historical Trends**: Multi-year revenue, gross profit, operating income, and net income charts.
- **Health Scoring & Risk Engine**:
  - Computes a 0–100 Financial Health Score and letter grade ($A^+$ to $F$).
  - Flags key strengths, critical solvency/valuation watchpoints, and generates Bull/Bear theses.
- **Multi-Format Export**: Terminal visual dashboard, structured `JSON`, `Markdown`, and responsive `HTML`.

---

## 🌐 Launch the Web Application

```bash
cd "C:/Users/DHANUSH NAYAK/company_analyzer"
python run_web.py --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.

---

## 💻 Command Line Usage

Analyze by ticker:
```bash
python main.py AAPL
```

Analyze by company name:
```bash
python main.py "NVIDIA"
```

Export reports to Markdown, JSON, and HTML:
```bash
python main.py MSFT --export json,md,html --outdir ./reports
```

Interactive shell mode:
```bash
python main.py --interactive
```

---

## 🐍 Python Library Usage

```python
from company_analyzer import CompanyAgent

agent = CompanyAgent()

# Run full analysis
result = agent.analyze(
    "NVDA",
    display=True,
    export_formats=["json", "html"],
    output_dir="./reports"
)

# Access structured data directly
print("Score:", result["scoring"]["overall_score"])
print("Grade:", result["scoring"]["grade"])
print("Strengths:", result["scoring"]["strengths"])
print("Risks:", result["scoring"]["risks"])
```

---

## ⚙️ Optional LLM Configuration

Works 100% offline & free using the built-in financial rule engine. To enable live LLM synthesis:

```bash
# Using OpenAI
set OPENAI_API_KEY=your_key_here

# Using Groq (ultra-fast Llama 3.3)
set GROQ_API_KEY=your_key_here

# Custom endpoint (Ollama / Local LLM)
python main.py AAPL --base-url http://localhost:11434/v1 --model llama3
```
