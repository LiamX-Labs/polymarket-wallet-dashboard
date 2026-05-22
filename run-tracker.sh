#!/bin/bash
# Market Tracker Runner Script for Polymarket Wallet Dashboard

cd "$(dirname "$0")"

# Load tracker environment variables
if [ -f .env.tracker ]; then
    export $(cat .env.tracker | grep -v '^#' | xargs)
fi

# Use conda's Python which has all required packages
# If conda is not available, fall back to system python3
if command -v conda &> /dev/null; then
    # Use conda's base environment python
    PYTHON_BIN="/home/william/anaconda3/bin/python"
else
    PYTHON_BIN="python3"
fi

# Run the market tracker
exec "$PYTHON_BIN" market_tracker.py
