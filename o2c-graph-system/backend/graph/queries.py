"""
Graph query operations - BFS, flow tracing, and broken flow detection.
"""

import networkx as nx
import logging
from typing import Dict, List, Set, Tuple, Any
from collections import deque

logger = logging.getLogger(__name__)


def trace_flow(graph: nx.DiGraph, start_node_id: str, depth: int = 4, max_nodes: int = 500) -> Dict:
    """
    Trace the flow from a start node using BFS.
    Returns all reachable nodes within specified depth.
    
    Args:
        graph: NetworkX DiGraph
        start_node_id: Starting node ID
        depth: Maximum traversal depth
        max_nodes: Maximum nodes to return (for performance)
    
    Returns:
        Dictionary with 'nodes' and 'edges' for the subgraph
    """
    if not graph.has_node(start_node_id):
        return {"error": f"Node {start_node_id} not found"}
    
    visited_nodes = set()
    visited_edges = set()
    queue = deque([(start_node_id, 0)])  # (node_id, current_depth)
    
    # BFS traversal
    while queue and len(visited_nodes) < max_nodes:
        current_node, current_depth = queue.popleft()
        
        if current_node in visited_nodes:
            continue
        
        visited_nodes.add(current_node)
        
        if current_depth < depth:
            # Add successors (outgoing edges)
            for successor in graph.successors(current_node):
                if successor not in visited_nodes:
                    queue.append((successor, current_depth + 1))
                    visited_edges.add((current_node, successor))
            
            # Add predecessors (incoming edges)
            for predecessor in graph.predecessors(current_node):
                if predecessor not in visited_nodes:
                    queue.append((predecessor, current_depth + 1))
                    visited_edges.add((predecessor, current_node))
    
    # Build result subgraph
    nodes = []
    for node_id in visited_nodes:
        node_data = graph.nodes[node_id]
        nodes.append({
            "id": node_id,
            "label": node_data.get("label", node_id),
            "type": node_data.get("type"),
            "color": node_data.get("color"),
            "icon": node_data.get("icon"),
            "val": node_data.get("val", 3),
            "properties": node_data.get("properties", {})
        })
    
    links = []
    for src, tgt in visited_edges:
        if graph.has_edge(src, tgt):
            edge_data = graph.edges[src, tgt]
            links.append({
                "source": src,
                "target": tgt,
                "relationship": edge_data.get("relationship")
            })
    
    return {
        "start_node": start_node_id,
        "nodes_explored": len(visited_nodes),
        "edges_explored": len(visited_edges),
        "nodes": nodes,
        "links": links
    }


def find_neighbors(graph: nx.DiGraph, node_id: str, depth: int = 1) -> Dict:
    """
    Find immediate neighbors with relationship types.
    
    Args:
        graph: NetworkX DiGraph
        node_id: Node ID to find neighbors for
        depth: How many hops to traverse
    
    Returns:
        Dictionary with incoming and outgoing neighbors
    """
    if not graph.has_node(node_id):
        return {"error": f"Node {node_id} not found"}
    
    incoming = []
    outgoing = []
    
    # Get outgoing neighbors
    for successor in graph.successors(node_id):
        edge_data = graph.edges[node_id, successor]
        successor_data = graph.nodes[successor]
        outgoing.append({
            "node_id": successor,
            "label": successor_data.get("label"),
            "type": successor_data.get("type"),
            "relationship": edge_data.get("relationship")
        })
    
    # Get incoming neighbors
    for predecessor in graph.predecessors(node_id):
        edge_data = graph.edges[predecessor, node_id]
        predecessor_data = graph.nodes[predecessor]
        incoming.append({
            "node_id": predecessor,
            "label": predecessor_data.get("label"),
            "type": predecessor_data.get("type"),
            "relationship": edge_data.get("relationship")
        })
    
    return {
        "node_id": node_id,
        "incoming": incoming,
        "outgoing": outgoing
    }


def find_broken_flows(graph: nx.DiGraph, db_executor=None) -> Dict:
    """
    Find incomplete O2C flows.
    
    Rules:
    - SalesOrder → SalesOrderItem → Delivery (must have all)
    - Delivery → BillingDocument (every delivery should have billing)
    - BillingDocument → JournalEntry (every billing should record)
    
    Returns:
        Dictionary with lists of problematic nodes
    """
    issues = {
        "orders_without_items": [],
        "items_without_material": [],
        "orders_not_delivered": [],
        "deliveries_not_billed": [],
        "billings_not_recorded": []
    }
    
    try:
        # Orders without items
        for node_id in graph.nodes():
            node_type = graph.nodes[node_id].get("type")
            
            if node_type == "SalesOrder":
                has_items = any(
                    graph.edges[node_id, successor].get("relationship") == "HAS_ITEM"
                    for successor in graph.successors(node_id)
                )
                if not has_items:
                    issues["orders_without_items"].append(node_id)
            
            # Items without material
            elif node_type == "SalesOrderItem":
                has_material = any(
                    graph.edges[node_id, successor].get("relationship") == "REFERENCES"
                    for successor in graph.successors(node_id)
                )
                if not has_material:
                    issues["items_without_material"].append(node_id)
            
            # Deliveries without billing
            elif node_type == "Delivery":
                has_billing = any(
                    graph.edges[predecessor, node_id].get("relationship") == "BILLS"
                    for predecessor in graph.predecessors(node_id)
                )
                if not has_billing:
                    issues["deliveries_not_billed"].append(node_id)
            
            # Billings without journal entries
            elif node_type == "BillingDocument":
                has_recording = any(
                    graph.edges[predecessor, node_id].get("relationship") == "RECORDS"
                    for predecessor in graph.predecessors(node_id)
                )
                if not has_recording:
                    issues["billings_not_recorded"].append(node_id)
        
        # Orders not delivered
        for node_id in graph.nodes():
            if graph.nodes[node_id].get("type") == "SalesOrder":
                has_delivery = any(
                    graph.edges[successor, node_id].get("relationship") == "FULFILLS"
                    for successor in graph.predecessors(node_id)
                )
                if not has_delivery:
                    issues["orders_not_delivered"].append(node_id)
    
    except Exception as e:
        logger.error(f"Error finding broken flows: {e}")
    
    return {
        "total_issues_found": sum(len(v) for v in issues.values()),
        "issues": issues
    }


def get_node_path(graph: nx.DiGraph, start_id: str, end_id: str) -> Dict:
    """
    Find shortest path between two nodes.
    
    Returns:
        Path as list of node IDs
    """
    try:
        # Try to find path in the graph (undirected for connectivity)
        undirected = graph.to_undirected()
        if nx.has_path(undirected, start_id, end_id):
            path = nx.shortest_path(undirected, start_id, end_id)
            return {"path": path, "distance": len(path) - 1}
        else:
            return {"error": "No path found between nodes"}
    except nx.NetworkXError as e:
        return {"error": str(e)}


def get_connected_components(graph: nx.DiGraph) -> Dict:
    """
    Find connected components in the graph.
    
    Returns:
        List of component sizes and analysis
    """
    undirected = graph.to_undirected()
    components = list(nx.connected_components(undirected))
    
    return {
        "num_components": len(components),
        "component_sizes": sorted([len(c) for c in components], reverse=True),
        "largest_component": len(components[0]) if components else 0,
        "is_connected": nx.is_connected(undirected)
    }
