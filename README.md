# KeeperPilot — Autonomous DeFi Operator

> A personal AI DeFi manager that watches your money 24/7 and takes action when opportunities appear.

KeeperPilot lets users delegate capital-management decisions to an AI agent while keeping control
through policies, transparency, and KeeperHub-powered execution.

**MVP action:** automatically move idle USDC to a better risk-adjusted yield opportunity.

## Architecture rule

KeeperHub is the **execution layer**. We do NOT rebuild transaction execution, blockchain routing,
gas optimization, MEV protection, or wallet infrastructure. The app layer only:

1. Monitors user positions
2. Analyzes yield opportunities (risk-adjusted)
3. Applies user-defined policies
4. Decides when an action is beneficial
5. Executes through KeeperHub (MCP server)
6. Records every decision and execution in an audit trail

## Repo layout

```
keeperpilot/
  frontend/    Next.js + TypeScript + Tailwind dashboard
  backend/     FastAPI application (user management, orchestration, API)
  agent/       AI reasoning, policy engine, yield intelligence, monitoring
  database/    SQLAlchemy models + Alembic migrations (PostgreSQL)
  docs/        Architecture, demo script, references
  tests/       Pytest suite
  docker-compose.yml
```

## Quick start (local dev)

### Backend

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"
cp .env.example .env            # fill secrets as needed
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:3000
```

### Database

```bash
docker compose up -d postgres   # or use any PostgreSQL instance
alembic -c database/alembic.ini upgrade head
```

## Environment

Copy `.env.example` to `.env`. KeeperHub is in **mock mode** by default
(`KEEPERHUB_MOCK=true`) so the whole stack runs without blockchain credentials.
