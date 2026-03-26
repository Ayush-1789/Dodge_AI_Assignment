"""
Graph data API endpoints - returns graph data for visualization.
"""

import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/graph", tags=["graph"])

# Will be set by main.py
graph_instance = None
graph_builder = None


def initialize_dependencies(builder):
    """Initialize dependencies (call from main.py)."""
    global graph_instance, graph_builder
    graph_builder = builder
    graph_instance = builder.graph


@router.get("/")
async def get_graph():
    """Return full graph as nodes + links JSON for visualization."""
    if graph_builder is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    from fastapi.responses import JSONResponse
    return JSONResponse(content=graph_builder.get_graph_json())


@router.get("/node/{node_id}")
async def get_node(node_id: str):
    """Return full property metadata for a node."""
    if graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    return graph_builder.get_node_metadata(node_id)


@router.get("/stats")
async def get_stats():
    """Return graph statistics."""
    if graph_builder is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    return graph_builder.get_graph_stats()


@router.get("/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = 1):
    """Return neighbor nodes for a given node."""
    from ..graph.queries import find_neighbors
    
    if graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    return find_neighbors(graph_instance, node_id, depth)


@router.get("/trace/{node_id}")
async def trace_node(node_id: str, depth: int = 4):
    """Trace flow from a node."""
    from ..graph.queries import trace_flow
    
    if graph_instance is None:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    return trace_flow(graph_instance, node_id, depth)
