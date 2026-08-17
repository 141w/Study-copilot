#!/usr/bin/env bash
# ============================================================
# run_all_tests.sh — Run all Study-copilot tests and report status
# Usage: ./scripts/run_all_tests.sh
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
PYTHON="${PYTHON:-/Users/wweiqi/miniconda3/envs/study-c/bin/python}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKEND_STATUS="SKIPPED"
FRONTEND_STATUS="SKIPPED"
BACKEND_COV=""
OVERALL=0

print_header() {
  echo ""
  echo "============================================================"
  echo "  Study-copilot — Full Test Suite"
  echo "  $(date)"
  echo "============================================================"
  echo ""
}

run_backend() {
  echo -e "${YELLOW}▶ Running backend tests...${NC}"
  cd "$BACKEND_DIR"

  if command -v "$PYTHON" &>/dev/null; then
    "$PYTHON" -m pytest tests/ -v --cov=app --cov-report=term-missing 2>&1 | tee /tmp/sc-backend.log
  elif command -v pytest &>/dev/null; then
    pytest tests/ -v --cov=app --cov-report=term-missing 2>&1 | tee /tmp/sc-backend.log
  else
    echo -e "${RED}ERROR: pytest not found and no Python specified${NC}"
    BACKEND_STATUS="ERROR"
    OVERALL=1
    return
  fi

  if [ ${PIPESTATUS[0]} -eq 0 ]; then
    BACKEND_STATUS="PASSED"
    # Extract coverage percentage from output
    BACKEND_COV=$(grep "^TOTAL" /tmp/sc-backend.log | awk '{print $NF}' || echo "N/A")
  else
    BACKEND_STATUS="FAILED"
    OVERALL=1
  fi
}

run_frontend() {
  echo -e "\n${YELLOW}▶ Running frontend tests...${NC}"
  cd "$FRONTEND_DIR"

  if ! command -v npm &>/dev/null; then
    echo -e "${RED}ERROR: npm not found${NC}"
    FRONTEND_STATUS="ERROR"
    OVERALL=1
    return
  fi

  npm test 2>&1 | tee /tmp/sc-frontend.log

  if [ ${PIPESTATUS[0]} -eq 0 ]; then
    FRONTEND_STATUS="PASSED"
  else
    FRONTEND_STATUS="FAILED"
    OVERALL=1
  fi
}

print_summary() {
  echo ""
  echo "============================================================"
  echo "  TEST RESULTS SUMMARY"
  echo "============================================================"
  echo ""

  # Backend
  if [ "$BACKEND_STATUS" = "PASSED" ]; then
    echo -e "  Backend:   ${GREEN}✔ PASSED${NC}  (coverage: ${BACKEND_COV:-N/A})"
  elif [ "$BACKEND_STATUS" = "FAILED" ]; then
    echo -e "  Backend:   ${RED}✘ FAILED${NC}"
  elif [ "$BACKEND_STATUS" = "ERROR" ]; then
    echo -e "  Backend:   ${RED}⚠ ERROR${NC}"
  else
    echo -e "  Backend:   ${YELLOW}⊘ SKIPPED${NC}"
  fi

  # Frontend
  if [ "$FRONTEND_STATUS" = "PASSED" ]; then
    echo -e "  Frontend:  ${GREEN}✔ PASSED${NC}"
  elif [ "$FRONTEND_STATUS" = "FAILED" ]; then
    echo -e "  Frontend:  ${RED}✘ FAILED${NC}"
  elif [ "$FRONTEND_STATUS" = "ERROR" ]; then
    echo -e "  Frontend:  ${RED}⚠ ERROR${NC}"
  else
    echo -e "  Frontend:  ${YELLOW}⊘ SKIPPED${NC}"
  fi

  echo ""
  if [ $OVERALL -eq 0 ]; then
    echo -e "  Overall:   ${GREEN}✔ ALL TESTS PASSED${NC}"
  else
    echo -e "  Overall:   ${RED}✘ SOME TESTS FAILED${NC}"
  fi
  echo "============================================================"
  echo ""
}

# ---- Main ----
print_header
run_backend
run_frontend
print_summary

exit $OVERALL
