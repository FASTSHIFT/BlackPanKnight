#!/bin/bash

# Auto-format script for BlackPanKnight

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  BlackPanKnight Code Formatter${NC}"
echo -e "${BLUE}================================================${NC}"

FIND_EXCLUDE=(
    -not -path "./__pycache__/*"
    -not -path "*/__pycache__/*"
    -not -path "./htmlcov/*"
    -not -path "./.venv/*"
    -not -path "./venv/*"
    -not -path "./.git/*"
    -not -path "./ref_project/*"
    -not -path "./project_src/*"
)

# Parse arguments
CHECK_ONLY=false
LINT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --check | -c)
            CHECK_ONLY=true
            shift
            ;;
        --lint | -l)
            LINT=true
            shift
            ;;
        --help | -h)
            echo "Usage: $0 [options]"
            echo "  --check, -c    Check only, no changes"
            echo "  --lint, -l     Run flake8 linting"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [ "$CHECK_ONLY" = true ]; then
    echo -e "${YELLOW}Running in check-only mode...${NC}"
fi

# Format Python
echo -e "\n${GREEN}Formatting Python files...${NC}"

FILES=$(find . -name "*.py" "${FIND_EXCLUDE[@]}" 2>/dev/null | sort)

if [ -z "$FILES" ]; then
    echo "   No Python files found"
    exit 0
fi

COUNT=$(echo "$FILES" | wc -l)

BLACK_ARGS="--quiet --line-length 88"
if [ "$CHECK_ONLY" = true ]; then
    BLACK_ARGS="--check --quiet --line-length 88"
fi

if python3 -m black $BLACK_ARGS $FILES 2>/dev/null; then
    if [ "$CHECK_ONLY" = true ]; then
        echo -e "   ${GREEN}Python: $COUNT file(s) check passed ✓${NC}"
    else
        echo -e "   ${GREEN}Python: $COUNT file(s) formatted ✓${NC}"
    fi
else
    echo -e "   ${RED}Python: formatting issues found ✗${NC}"
    if [ "$CHECK_ONLY" = true ]; then
        exit 1
    fi
fi

# Lint
if [ "$LINT" = true ]; then
    echo -e "\n${GREEN}Linting Python files...${NC}"
    if python3 -m flake8 --ignore=E501,W503,E203 --max-line-length=120 $FILES 2>/dev/null; then
        echo -e "   ${GREEN}All files passed linting ✓${NC}"
    else
        echo -e "   ${YELLOW}Linting warnings found${NC}"
    fi
fi

echo -e "\n${GREEN}Done!${NC}"
