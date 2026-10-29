#!/usr/bin/env bash
set -euo pipefail

# Determine repository directory
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Starting Profile Card & Snake Update ==="

# Check for local GitHub CLI token if gh is available
if command -v gh &> /dev/null; then
  echo "[*] Retrieving local GitHub CLI auth token..."
  GH_TOKEN_VAL="$(gh auth token 2>/dev/null || true)"
  if [ -n "$GH_TOKEN_VAL" ]; then
    export GH_TOKEN="$GH_TOKEN_VAL"
    echo "[✓] Successfully loaded GH_TOKEN from local GitHub CLI."
  else
    echo "[!] gh is installed but not authenticated. Falling back to public stats."
  fi
else
  echo "[*] GitHub CLI ('gh') not in PATH. Falling back to public GitHub stats."
fi

# Run generate.py (Python Standard Library only)
if [ ! -f "dots.json" ]; then
  echo "[*] dots.json not found. Running portrait.py first..."
  if [ -f "../public/Bullish PFP 2.png" ]; then
    python3 portrait.py "../public/Bullish PFP 2.png" dots.json
  else
    echo "[-] Portrait image not found. Please provide an avatar image to portrait.py."
    exit 1
  fi
fi

python3 generate.py dots.json

# Check if any SVG files changed
if git diff --quiet dark.svg light.svg snake.svg 2>/dev/null; then
  echo "[✓] SVGs are already up to date. No git commit needed."
else
  echo "[*] SVG updates detected. Staging and committing..."
  git add dark.svg light.svg snake.svg
  git commit -m "Auto-update profile terminal & contribution snake [skip ci]"
  
  # Push if remote is configured
  if git remote get-url origin &>/dev/null; then
    echo "[*] Pushing to origin..."
    git push origin HEAD
    echo "[✓] Successfully pushed fresh SVGs to GitHub!"
  else
    echo "[!] No git remote 'origin' configured yet. Changes committed locally."
  fi
fi

echo "=== Update Completed Successfully ==="
