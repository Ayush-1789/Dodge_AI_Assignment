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

Start backend:

```bash
cd backend
python main.py
```

Data ingestion behavior:
- Automatic: On backend startup, if `backend/data/o2c.db` is missing or incomplete, data is rebuilt automatically from `sap-o2c-data`.
- No separate ingestion file is required for normal usage.
- Optional manual full rebuild:

```bash
cd backend
python database/init_db.py
```

### 2. Frontend Setup

```bash
cd frontend
npm install
```

```bash
cd frontend
npm run dev
```

## URLs

- Frontend: `http://localhost:5173` (or next free Vite port)
- Backend API: `http://localhost:8000`
- Health check: `http://localhost:8000/health`

## Graph + Chat Behavior

When the assistant returns `highlighted_nodes`, the frontend:
- Highlights the source nodes
- Focuses camera on those nodes
- Keeps them easy to inspect and click for details

## Troubleshooting

- `Port in use`: set a different `PORT` in `backend/.env` and restart:

```env
PORT=8010
```

- `LLM service not available`: check `backend/.env` and ensure `GEMINI_API_KEY` is set
- Empty graph: verify `sap-o2c-data` exists and backend startup logs show successful initialization
