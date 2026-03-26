"""
Graph builder - constructs NetworkX property graph from SQLite database.
Creates nodes and edges based on schema definitions and database content.
"""

import networkx as nx
import sqlite3
import json
import logging
from typing import Dict, List, Tuple, Any
from .schema import NODE_TYPES, EDGE_TYPES, TABLE_TO_NODE_TYPE

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and maintains the O2C context graph."""
    
    def __init__(self, db_path: str):
        """Initialize graph builder with database path."""
        self.db_path = db_path
        self.graph = nx.DiGraph()
        self.node_count = 0
        self.edge_count = 0

    def _build_node_id(self, node_type: str, config: Dict, row_data: Dict, prefix: str = None) -> Tuple[str, List[str]]:
        """Build a stable node ID from one or more key columns."""
        key_cols = config.get("node_key_cols") or [config["id_col"]]
        key_values: List[str] = []

        for col in key_cols:
            key = f"{prefix}_{col}" if prefix else col
            value = row_data.get(key)
            if value is None or value == "":
                return None, []
            key_values.append(str(value).strip())

        raw_id = "__".join(key_values)
        return f"{node_type}_{raw_id}", key_values
    
    def build_graph(self, limit_per_entity: int = None) -> nx.DiGraph:
        """
        Build the complete context graph from database.
        
        Args:
            limit_per_entity: Optional limit on rows per entity type (for testing)
        
        Returns:
            NetworkX DiGraph with nodes and edges
        """
        logger.info("Starting graph construction...")
        
        # Add nodes from each entity type
        for node_type, config in NODE_TYPES.items():
            self._add_nodes_for_type(node_type, config, limit_per_entity)
        
        logger.info(f"Created {self.node_count} nodes")
        
        # Add edges based on relationships
        for source_type, target_type, rel_name, src_col, tgt_col in EDGE_TYPES:
            self._add_edges_for_relationship(
                source_type, target_type, rel_name, src_col, tgt_col, limit_per_entity
            )
        
        logger.info(f"Created {self.edge_count} edges")
        logger.info(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
        return self.graph
    
    def _add_nodes_for_type(self, node_type: str, config: Dict, limit: int = None):
        """Add nodes for a specific entity type."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            table = config["table"]
            id_col = config["id_col"]
            
            # Build SELECT query
            sql = f'SELECT * FROM "{table}"'
            if limit:
                sql += f' LIMIT {limit}'
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            for row in rows:
                row_dict = dict(row)
                full_node_id, key_values = self._build_node_id(node_type, config, row_dict)
                if not full_node_id:
                    continue

                # Extract label
                label = " / ".join(key_values) if len(key_values) > 1 else key_values[0]
                for label_col in config.get("label_cols", [id_col]):
                    if label_col in row_dict and row_dict[label_col]:
                        label = str(row_dict[label_col])
                        break
                
                # Add node with properties
                self.graph.add_node(
                    full_node_id,
                    type=node_type,
                    label=label,
                    color=config["color"],
                    icon=config["icon"],
                    properties=row_dict,
                    val=3  # Node size
                )
                
                self.node_count += 1
            
            conn.close()
            logger.info(f"Added {len(rows)} nodes of type {node_type}")
        
        except Exception as e:
            logger.error(f"Error adding nodes for {node_type}: {e}")
    
    def _add_edges_for_relationship(
        self,
        source_type: str,
        target_type: str,
        rel_name: str,
        src_col: str,
        tgt_col: str,
        limit: int = None
    ):
        """Add edges for a specific relationship type."""
        try:
            src_config = NODE_TYPES.get(source_type)
            tgt_config = NODE_TYPES.get(target_type)
            
            if not src_config or not tgt_config:
                logger.warning(f"Missing config for {source_type} or {target_type}")
                return
            
            src_table = src_config["table"]
            tgt_table = tgt_config["table"]
            src_id_col = src_config["id_col"]
            tgt_id_col = tgt_config["id_col"]
            src_key_cols = src_config.get("node_key_cols") or [src_id_col]
            tgt_key_cols = tgt_config.get("node_key_cols") or [tgt_id_col]
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Join source and target tables to find relationships
            src_selects = [f's."{col}" as src_{col}' for col in src_key_cols]
            tgt_selects = [f't."{col}" as tgt_{col}' for col in tgt_key_cols]
            sql = f"""
            SELECT DISTINCT
                {', '.join(src_selects + tgt_selects)}
            FROM "{src_table}" s
            INNER JOIN "{tgt_table}" t ON s."{src_col}" = t."{tgt_col}"
            WHERE s."{src_col}" IS NOT NULL AND t."{tgt_col}" IS NOT NULL
            """
            
            if limit:
                sql += f' LIMIT {limit}'
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            
            edge_count_for_rel = 0
            for row in rows:
                row_dict = dict(row)
                full_src_id, _ = self._build_node_id(source_type, src_config, row_dict, prefix="src")
                full_tgt_id, _ = self._build_node_id(target_type, tgt_config, row_dict, prefix="tgt")

                if not full_src_id or not full_tgt_id:
                    continue

                # Only add edge if both nodes exist
                if self.graph.has_node(full_src_id) and self.graph.has_node(full_tgt_id):
                    self.graph.add_edge(
                        full_src_id,
                        full_tgt_id,
                        relationship=rel_name
                    )
                    edge_count_for_rel += 1
                    self.edge_count += 1
            
            if edge_count_for_rel > 0:
                logger.info(f"Added {edge_count_for_rel} {source_type}→{target_type} ({rel_name}) edges")
            
            conn.close()
        
        except Exception as e:
            logger.error(f"Error adding edges for {source_type}→{target_type}: {e}")
    
    def get_graph_json(self) -> Dict:
        """
        Export filtered graph as JSON for visualization (react-force-graph-2d format).
        Only includes core O2C node types and valid edges between them.
        """
        # Core node types to include
        allowed_types = {
            "SalesOrder", "SalesOrderItem", "Customer", "Material",
            "Delivery", "BillingDocument", "JournalEntry", "Address"
        }

        # Filter nodes
        nodes = []
        allowed_node_ids = set()
        for node_id, node_data in self.graph.nodes(data=True):
            if node_data.get("type") in allowed_types:
                nodes.append({
                    "id": node_id,
                    "label": node_data.get("label", node_id),
                    "type": node_data.get("type"),
                    "color": node_data.get("color"),
                    "icon": node_data.get("icon"),
                    "val": node_data.get("val", 3),
                    "properties": node_data.get("properties", {})
                })
                allowed_node_ids.add(node_id)

        # Filter links to only those between allowed nodes
        links = []
        for src, tgt in self.graph.edges():
            if src in allowed_node_ids and tgt in allowed_node_ids:
                edge_data = self.graph.edges[src, tgt]
                links.append({
                    "source": src,
                    "target": tgt,
                    "relationship": edge_data.get("relationship")
                })

        return {
            "nodes": nodes,
            "links": links
        }
    
    def get_node_metadata(self, node_id: str) -> Dict:
        """Get full metadata for a node."""
        if not self.graph.has_node(node_id):
            return {"error": "Node not found"}
        
        node_data = self.graph.nodes[node_id]
        
        return {
            "id": node_id,
            "type": node_data.get("type"),
            "label": node_data.get("label"),
            "color": node_data.get("color"),
            "icon": node_data.get("icon"),
            "properties": node_data.get("properties", {}),
            "in_degree": self.graph.in_degree(node_id),
            "out_degree": self.graph.out_degree(node_id)
        }
    
    def get_graph_stats(self) -> Dict:
        """Get statistics about the graph."""
        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "node_types": self._count_by_type(),
            "density": nx.density(self.graph)
        }
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count nodes by type."""
        counts = {}
        for node_id in self.graph.nodes():
            node_type = self.graph.nodes[node_id].get("type")
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts


# Global graph instance
_graph_instance = None


def get_builder(db_path: str) -> GraphBuilder:
    """Get or create graph builder instance."""
    return GraphBuilder(db_path)


def build_and_cache_graph(db_path: str, force_rebuild: bool = False) -> nx.DiGraph:
    """Build and cache the graph globally."""
    global _graph_instance
    
    if _graph_instance is None or force_rebuild:
        builder = get_builder(db_path)
        _graph_instance = builder.build_graph()
    
    return _graph_instance
