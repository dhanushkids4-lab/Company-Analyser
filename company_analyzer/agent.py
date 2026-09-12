import os
from typing import Dict, Any, Optional, List

from .data_fetcher import CompanyDataFetcher
from .financial_scorer import FinancialScorer
from .llm_analyzer import LLMAnalyzer
from .formatter import ReportFormatter


class CompanyAgent:
    """
    Autonomous Company & Financial Analysis Agent.
    Fetches real-time market data, calculates health scores, generates bull/bear theses,
    synthesizes strategic memos, and exports reports.
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None):
        self.fetcher = CompanyDataFetcher()
        self.scorer = FinancialScorer()
        self.llm = LLMAnalyzer(api_key=api_key, base_url=base_url, model=model)
        self.formatter = ReportFormatter()

    def analyze(
        self,
        company_query: str,
        use_llm: bool = True,
        display: bool = True,
        export_formats: Optional[List[str]] = None,
        output_dir: str = "."
    ) -> Dict[str, Any]:
        """
        Executes end-to-end analysis on a company ticker or name.
        """
        # 1. Fetch raw data & fundamentals
        company_data = self.fetcher.fetch_company_data(company_query)
        symbol = company_data.get("profile", {}).get("symbol", company_query.upper())

        # 2. Evaluate financial health & score
        score_data = self.scorer.evaluate(company_data)

        # 3. Synthesize strategic analysis memo (LLM or rule-based fallback)
        memo = None
        if use_llm:
            memo = self.llm.generate_analysis(company_data, score_data)

        # 4. Display terminal dashboard if requested
        if display:
            self.formatter.display_rich(company_data, score_data, memo)

        # 5. Export reports if specified
        exported_files = {}
        if export_formats:
            os.makedirs(output_dir, exist_ok=True)
            clean_sym = symbol.replace(".", "_").replace("/", "_")

            if "json" in export_formats:
                json_path = os.path.join(output_dir, f"{clean_sym}_analysis.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    f.write(self.formatter.to_json(company_data, score_data, memo))
                exported_files["json"] = json_path

            if "md" in export_formats or "markdown" in export_formats:
                md_path = os.path.join(output_dir, f"{clean_sym}_analysis.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(self.formatter.to_markdown(company_data, score_data, memo))
                exported_files["md"] = md_path

            if "html" in export_formats:
                html_path = os.path.join(output_dir, f"{clean_sym}_analysis.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(self.formatter.to_html(company_data, score_data, memo))
                exported_files["html"] = html_path

        return {
            "symbol": symbol,
            "company_data": company_data,
            "scoring": score_data,
            "memo": memo,
            "exported_files": exported_files
        }
