import sys
import argparse
from typing import List
from rich.console import Console
from rich.prompt import Prompt

from .agent import CompanyAgent


def run_interactive(agent: CompanyAgent, export_formats: List[str], output_dir: str):
    console = Console()
    console.print("\n[bold cyan]🚀 Company Financial & Valuation Agent (Interactive Mode)[/bold cyan]")
    console.print("[dim]Type any company ticker or name (e.g., 'NVDA', 'Apple', 'RELIANCE.NS', 'Tesla'), or 'exit'/'quit' to finish.[/dim]\n")

    while True:
        try:
            query = Prompt.ask("[bold green]Company Ticker / Name[/bold green]").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye![/dim]")
                break

            console.print(f"\n[cyan]🔍 Fetching and analyzing [bold]{query}[/bold]...[/cyan]")
            result = agent.analyze(
                query,
                display=True,
                export_formats=export_formats,
                output_dir=output_dir
            )

            exported = result.get("exported_files", {})
            if exported:
                console.print(f"[green]📁 Exported reports:[/green] {', '.join(exported.values())}\n")

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Exiting...[/dim]")
            break
        except Exception as e:
            console.print(f"[bold red]❌ Error analyzing {query}:[/bold red] {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous Company Financial & Valuation Analysis Agent"
    )
    parser.add_argument(
        "company",
        nargs="?",
        help="Company ticker (e.g. AAPL, TSLA, INFY.NS) or company name (e.g. 'Apple', 'NVIDIA')"
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive prompt mode"
    )
    parser.add_argument(
        "--export",
        type=str,
        default="",
        help="Comma-separated export formats: json, md, html (e.g. --export json,md,html)"
    )
    parser.add_argument(
        "-o", "--outdir",
        type=str,
        default=".",
        help="Output directory for exported files (default: current directory)"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM synthesis and rely strictly on the built-in financial rule engine"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model identifier (e.g. gpt-4o-mini, llama-3.3-70b-versatile)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API Key (defaults to OPENAI_API_KEY, GROQ_API_KEY, or OPENROUTER_API_KEY env vars)"
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Custom OpenAI-compatible API base URL"
    )

    args = parser.parse_args()

    export_formats = [f.strip().lower() for f in args.export.split(",") if f.strip()]

    agent = CompanyAgent(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model
    )

    if args.interactive or not args.company:
        run_interactive(agent, export_formats, args.outdir)
    else:
        console = Console()
        console.print(f"\n[cyan]🔍 Fetching and analyzing [bold]{args.company}[/bold]...[/cyan]")
        result = agent.analyze(
            args.company,
            use_llm=not args.no_llm,
            display=True,
            export_formats=export_formats,
            output_dir=args.outdir
        )
        exported = result.get("exported_files", {})
        if exported:
            console.print(f"[green]📁 Exported reports:[/green] {', '.join(exported.values())}\n")


if __name__ == "__main__":
    main()
