#!/bin/bash
# Push updates to GitHub so Render redeploys automatically
cd "$(dirname "$0")"
git add .
git commit -m "Fix Render deploy: add render.yaml blueprint, healthcheck endpoint, render_start.py"
git push origin main
echo "Pushed to GitHub! Render will auto-redeploy now."