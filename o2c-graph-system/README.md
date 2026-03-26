# O2C Context Graph System

Interactive Order-to-Cash (O2C) graph explorer with a conversational assistant.

The project combines:
- FastAPI backend for ingestion, SQL queries, graph traversal, and chat orchestration
- NetworkX property graph for business entity relationships
- React + react-force-graph frontend for interactive graph exploration
- Gemini-based NL-to-query and response synthesis pipeline

## Core Capabilities

- Interactive knowledge-graph view of O2C entities and relationships
- Chat-driven querying with highlighted and focused source nodes
- Node inspection UI for relationship and property drill-down
- Guardrails for off-topic and unsafe query handling
- Automatic SQLite initialization from JSONL source files

## Tech Stack

- Backend: Python, FastAPI, NetworkX, SQLite
- Frontend: React, Vite, react-force-graph-2d
- LLM: Google Gemini (`GEMINI_API_KEY`)

## Project Structure

```text
o2c-graph-system/
├── backend/
│   ├── api/
│   ├── database/
│   ├── graph/
│   ├── llm/
│   ├── data/
│   ├── main.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
├── sap-o2c-data/
├── run_backend.py
└── README.md
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm 10+
- Gemini API key

## Setup

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set your API key in `backend/.env`:

```env
GEMINI_API_KEY=your_api_key_here
ENV=development
PORT=8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

## Streamlined Run (Recommended)

From repo root:

```bash
python run_backend.py --reload
```

What this does:
- Starts FastAPI app
- Rebuilds database automatically if missing or incomplete
- Handles port fallback if requested port is already busy

In another terminal:

```bash
cd frontend
npm run dev
```

## URLs

- Frontend: `http://localhost:5173` (or next free Vite port)
- Backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## API Endpoints

- `POST /api/chat/`
- `GET /api/graph/`
- `GET /api/graph/node/{node_id}`

## Graph + Chat Behavior

When the assistant returns `highlighted_nodes`, the frontend now:
- Highlights the source nodes
- Focuses camera on those nodes
- Keeps them easy to inspect and click for details

## Development Notes

- Backend should be started from repo root using `run_backend.py`
- Frontend API calls are proxied by Vite (`/api` -> `http://localhost:8000`)
- Do not commit secrets; `.env` is ignored

## Troubleshooting

- `Port in use`: rerun backend with a different port:

```bash
python run_backend.py --reload --port 8010
```

- `LLM service not available`: check `backend/.env` and ensure `GEMINI_API_KEY` is set
- Empty graph: verify `sap-o2c-data` exists and backend startup logs show successful initialization

## GitHub Initialization

From repo root:

```bash
git init
git add .
git commit -m "Initial clean commit: O2C graph system"
```

## License

Use your preferred license for publication (MIT is a common choice).
