"""
Main FastAPI application for Order-to-Cash Context Graph System.
"""

import logging
import os
import sqlite3
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

try:
    from .database.init_db import init_database
    from .database.sql_executor import SQLExecutor
    from .graph.builder import get_builder
    from .api import chat, graph_data
except ImportError:
    # Support running `python main.py` from inside backend/.
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.database.init_db import init_database
    from backend.database.sql_executor import SQLExecutor
    from backend.graph.builder import get_builder
    from backend.api import chat, graph_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Find database and data paths
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
DB_DIR = BACKEND_DIR / "data"
DB_PATH = DB_DIR / "o2c.db"

# Load environment variables from backend/.env first, then project root .env.
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")


def resolve_data_dir() -> Path:
    """Resolve source data directory across local and deployment layouts."""
    env_override = os.environ.get("O2C_DATA_DIR") or os.environ.get("DATA_DIR")
    if env_override:
        return Path(env_override).expanduser().resolve()

    candidates = [
        PROJECT_DIR / "sap-o2c-data",
        PROJECT_DIR.parent / "sap-o2c-data",
        BACKEND_DIR / "sap-o2c-data",
    ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    # Return default candidate if none exist so error messages remain predictable.
    return candidates[0]


DATA_DIR = resolve_data_dir()

logger.info(f"Backend dir: {BACKEND_DIR}")
logger.info(f"Project dir: {PROJECT_DIR}")
logger.info(f"Data dir: {DATA_DIR}")


def is_database_healthy(db_path: Path) -> bool:
    """Validate that critical graph tables exist and contain data."""
    required_tables = [
        "sales_order_headers",
        "sales_order_items",
        "business_partners",
        "billing_document_headers"
    ]

    if not db_path.exists():
        return False

    conn = None
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        for table in required_tables:
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cursor.fetchone()[0] == 0:
                logger.warning(f"Database health check failed: missing table {table}")
                return False

            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            row_count = cursor.fetchone()[0]
            if row_count <= 0:
                logger.warning(f"Database health check failed: table {table} is empty")
                return False

        return True
    except Exception as exc:
        logger.warning(f"Database health check failed due to error: {exc}")
        return False
    finally:
        if conn is not None:
            conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App initialization and cleanup."""
    logger.info("Starting O2C Graph System...")
    
    try:
        # Initialize database if needed
        if not is_database_healthy(DB_PATH):
            if not DATA_DIR.exists():
                raise FileNotFoundError(
                    "Source data directory not found. Checked: "
                    f"{PROJECT_DIR / 'sap-o2c-data'} and {PROJECT_DIR.parent / 'sap-o2c-data'}. "
                    "Set O2C_DATA_DIR (or DATA_DIR) to the correct path, or include sap-o2c-data in your deploy."
                )
            logger.info("Database is missing or incomplete. Rebuilding from source files...")
            init_database(str(DB_PATH), str(DATA_DIR))
        
        # Build graph
        logger.info("Building graph...")
        sql_executor = SQLExecutor(str(DB_PATH))
        builder = get_builder(str(DB_PATH))
        graph = builder.build_graph()
        
        # Initialize API dependencies
        chat.initialize_dependencies(str(DB_PATH), graph)
        graph_data.initialize_dependencies(builder)
        
        logger.info("System initialization complete")
    
    except Exception as e:
        logger.error(f"Initialization error: {e}", exc_info=True)
        raise
    
    yield
    
    logger.info("Shutting down O2C Graph System...")


# Create FastAPI app
app = FastAPI(
    title="Order-to-Cash Context Graph System",
    description="Interactive graph visualization and conversational querying of O2C data",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router)
app.include_router(graph_data.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "status": "running",
        "message": "Order-to-Cash Context Graph System API",
        "endpoints": {
            "chat": "/api/chat",
            "graph": "/api/graph",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    from pathlib import Path

    current_dir = Path.cwd().resolve()
    backend_dir = BACKEND_DIR.resolve()
    app_ref = "main:app" if current_dir == backend_dir else "backend.main:app"
    
    uvicorn.run(
        app_ref,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=os.environ.get("ENV") != "production"
    )
