#!/usr/bin/env python
import os
import sys
import argparse
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    parser = argparse.ArgumentParser(description="Run Company Analyzer Web Interface")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)), help="Port number")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"🚀 Launching Company Financial & Valuation Analyzer Web")
    print(f"🌐 Access Dashboard at: http://{args.host}:{args.port}")
    print(f"=======================================================\n")

    uvicorn.run("web.app:app", host=args.host, port=args.port, reload=args.reload)

if __name__ == "__main__":
    main()
