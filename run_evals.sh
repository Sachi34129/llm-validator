#!/bin/bash
# Script to run promptfoo evals with environment variables loaded

# Load environment variables from .env file
if [ -f .env ]; then
    # Use a safer method to load .env file
    set -a
    source .env
    set +a
fi

# Verify API key is loaded
if [ -z "$GEMINI_API_KEY" ]; then
    echo "ERROR: GEMINI_API_KEY not found in .env file or environment"
    echo "Please make sure your .env file contains: GEMINI_API_KEY=your_key_here"
    exit 1
fi

echo "✓ GEMINI_API_KEY loaded (${#GEMINI_API_KEY} characters)"

# Run promptfoo eval
npx promptfoo eval
