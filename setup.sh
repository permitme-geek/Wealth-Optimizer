#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# WealthOS — One-Command Setup
# Run this once from the wealthos/ directory:
#   chmod +x setup.sh && ./setup.sh
# ─────────────────────────────────────────────────────────────────
set -e

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'   # No Colour

echo -e "${CYAN}${BOLD}"
echo "  ██╗    ██╗███████╗ █████╗ ██╗  ████████╗██╗  ██╗ ██████╗ ███████╗"
echo "  ██║    ██║██╔════╝██╔══██╗██║  ╚══██╔══╝██║  ██║██╔═══██╗██╔════╝"
echo "  ██║ █╗ ██║█████╗  ███████║██║     ██║   ███████║██║   ██║███████╗"
echo "  ██║███╗██║██╔══╝  ██╔══██║██║     ██║   ██╔══██║██║   ██║╚════██║"
echo "  ╚███╔███╔╝███████╗██║  ██║███████╗██║   ██║  ██║╚██████╔╝███████║"
echo "   ╚══╝╚══╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"
echo -e "${NC}"
echo -e "${BOLD}  Real-Time AI Wealth Optimization — Twinkle and Blink Consulting${NC}"
echo ""

# ── Step 1: Check Python version ──────────────────────────────
echo -e "${BOLD}[1/5] Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
required="3.10"
if python3 -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)"; then
    echo -e "  ${GREEN}✓ Python ${python_version} — OK${NC}"
else
    echo -e "  ${RED}✗ Python 3.10+ required. Current: ${python_version}${NC}"
    echo "    Install via: brew install python@3.11"
    exit 1
fi

# ── Step 2: Create virtual environment ────────────────────────
echo -e "\n${BOLD}[2/5] Creating virtual environment (.venv)...${NC}"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "  ${YELLOW}⚠ .venv already exists — skipping${NC}"
fi

source .venv/bin/activate

# ── Step 3: Install dependencies ──────────────────────────────
echo -e "\n${BOLD}[3/5] Installing dependencies (this takes ~60 seconds)...${NC}"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo -e "  ${GREEN}✓ All packages installed${NC}"

# ── Step 4: Create .env from template ─────────────────────────
echo -e "\n${BOLD}[4/5] Setting up environment configuration...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${GREEN}✓ .env created from template${NC}"
    echo -e "  ${YELLOW}→ Edit .env now and fill in your values${NC}"
else
    echo -e "  ${YELLOW}⚠ .env already exists — not overwritten${NC}"
fi

# ── Step 5: Verify installation ───────────────────────────────
echo -e "\n${BOLD}[5/5] Verifying installation...${NC}"
python3 -c "
import importlib.metadata
for pkg in ['numpy', 'scipy', 'rich', 'typer', 'pydantic']:
    try:
        version = importlib.metadata.version(pkg)
        print(f'  \033[0;32m✓ {pkg} {version}\033[0m')
    except importlib.metadata.PackageNotFoundError:
        print(f'  \033[0;31m✗ {pkg} not found\033[0m')
"

# ── Done ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}  ✓ WealthOS setup complete!${NC}"
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BOLD}  Next steps:${NC}"
echo ""
echo -e "  ${CYAN}1. Fill in your credentials:${NC}"
echo -e "     nano .env"
echo ""
echo -e "  ${CYAN}2. Activate the virtual environment (every new terminal):${NC}"
echo -e "     source .venv/bin/activate"
echo ""
echo -e "  ${CYAN}3. Personalize your profile, KPIs, accounts and goals:${NC}"
echo -e "     python cli.py setup"
echo ""
echo -e "  ${CYAN}4. Run your first full optimization:${NC}"
echo -e "     python cli.py report"
echo ""
echo -e "  ${CYAN}5. Once .env keys are filled in, pull live data:${NC}"
echo -e "     python cli.py sync"
echo ""
echo -e "  ${BOLD}Daily workflow:${NC}"
echo -e "     python cli.py sync && python cli.py report"
echo -e "     python cli.py daily-schedule  # activate 8 AM daily briefs"
echo ""
