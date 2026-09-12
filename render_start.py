#!/usr/bin/env python
"""Render.com start command: binds to $PORT from the platform environment."""
import os
import sys
import uvicorn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    print(f"🚀 Starting Company Analyzer on 0.0.0.0:{port}")
    uvicorn.run("web.app:app", host="0.0.0.0", port=port)