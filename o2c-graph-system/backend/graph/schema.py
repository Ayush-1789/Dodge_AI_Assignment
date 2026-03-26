"""
Graph schema definition for O2C Context Graph.
Defines node types, edge types, and their relationships.
"""

# Node types with properties for visualization and identification
NODE_TYPES = {
    "SalesOrder": {
        "color": "#4A90D9",
        "icon": "📦",
        "table": "sales_order_headers",
        "id_col": "sales_order",
        "label_cols": ["sales_order", "sold_to_party"]
    },
    "SalesOrderItem": {
        "color": "#5BA85A",
        "icon": "📋",
        "table": "sales_order_items",
        "id_col": "sales_order_item",
        "node_key_cols": ["sales_order", "sales_order_item"],
        "label_cols": ["sales_order_item", "material"]
    },
    "Customer": {
        "color": "#E8A838",
        "icon": "👤",
        "table": "business_partners",
        "id_col": "business_partner",
        "label_cols": ["business_partner", "business_partner_full_name"]
    },
    "Material": {
        "color": "#9B59B6",
        "icon": "🔧",
        "table": "products",
        "id_col": "product",
        "label_cols": ["product"]
    },
    "Delivery": {
        "color": "#E74C3C",
        "icon": "🚚",
        "table": "outbound_delivery_headers",
        "id_col": "delivery_document",
        "label_cols": ["delivery_document", "shipping_point"]
    },
    "BillingDocument": {
        "color": "#1ABC9C",
        "icon": "🧾",
        "table": "billing_document_headers",
        "id_col": "billing_document",
        "label_cols": ["billing_document", "sold_to_party"]
    },
    "JournalEntry": {
        "color": "#F39C12",
        "icon": "📒",
        "table": "journal_entry_items_accounts_receivable",
        "id_col": "accounting_document",
        "label_cols": ["accounting_document"]
    },
    "Address": {
        "color": "#95A5A6",
        "icon": "📍",
        "table": "business_partner_addresses",
        "id_col": "address_id",
        "label_cols": ["address_id", "city_name"]
    },
    "Plant": {
        "color": "#16A34A",
        "icon": "🏭",
        "table": "plants",
        "id_col": "plant",
        "label_cols": ["plant"]
    },
}

# Edge types defining relationships between nodes
# Format: (source_node_type, target_node_type, relationship_name, source_col, target_col)
EDGE_TYPES = [
    # Sales Order flow
    ("SalesOrder", "SalesOrderItem", "HAS_ITEM", "sales_order", "sales_order"),
    ("SalesOrder", "Customer", "PLACED_BY", "sold_to_party", "business_partner"),
    
    # Order item to material
    ("SalesOrderItem", "Material", "REFERENCES", "material", "product"),
    
    # Delivery relationships (no direct customer link - would go through sales order items)
    # Removed: Delivery → Customer because outbound_delivery_headers has no sold_to_party
    
    # Billing relationships (using reference_sd_document from billing to link to orders)
    ("BillingDocument", "Customer", "INVOICES", "sold_to_party", "business_partner"),
    
    # Journal entry relationships (using reference_document from journal to link to billing)
    ("JournalEntry", "BillingDocument", "RECORDS", "accounting_document", "accounting_document"),
    
    # Customer address relationships
    ("Customer", "Address", "HAS_ADDRESS", "business_partner", "business_partner"),
]

# Map table names to node types (for reverse lookup)
TABLE_TO_NODE_TYPE = {v["table"]: k for k, v in NODE_TYPES.items()}
