#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Defaults (override with environment variables) ────────────────────────────
NNSD_URL="${NNSD_URL:-http://localhost:8080}"
NNSD_KEY="${NNSD_KEY:-admin-secret-key-change-me}"
TOX21_DATA="${TOX21_DATA:-/opt/neural/data/tox21}"
TOX21_PORT="${TOX21_PORT:-8081}"

export NNSD_URL NNSD_KEY TOX21_DATA TOX21_PORT

# ── Check dependencies ────────────────────────────────────────────────────────
if ! python3 -c "import flask, requests" 2>/dev/null; then
    echo "Installing Python dependencies..."
    python3 -m pip install flask requests
fi

if ! python3 -c "from rdkit import Chem" 2>/dev/null; then
    echo "WARNING: RDKit not found — SMILES conversion will be unavailable."
    echo "         Install with: pip3 install rdkit"
fi

echo "Starting tox21_demo (foreground)"
echo "  nnsd_client: $NNSD_URL"
echo "  Data root  : $TOX21_DATA"
echo "  HTTP port  : $TOX21_PORT"
echo ""

exec python3 "$SCRIPT_DIR/app.py"
