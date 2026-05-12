#!/bin/bash
# Run all tests with coverage check.
# Usage: ./run_tests.sh [--html]
#   --html  Generate HTML coverage report in htmlcov/

set -e

MIN_COVERAGE=80
COV_ARGS="--cov=src --cov-report=term-missing --cov-fail-under=$MIN_COVERAGE"

if [[ "$1" == "--html" ]]; then
    COV_ARGS="$COV_ARGS --cov-report=html"
fi

echo "================================================"
echo "  BlackPanKnight Test Suite"
echo "  Minimum coverage: ${MIN_COVERAGE}%"
echo "================================================"
echo

python -m pytest tests/ -v $COV_ARGS --durations=10

echo
echo "================================================"
echo "  All tests passed, coverage >= ${MIN_COVERAGE}%"
echo "================================================"
