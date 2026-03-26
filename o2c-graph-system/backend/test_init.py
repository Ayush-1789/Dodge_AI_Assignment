#!/usr/bin/env python
"""
Test script for O2C database initialization and verification.
"""

import sys
import os
import sqlite3

# Add backend to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from database.init_db import init_database
from database.sql_executor import SQLExecutor
from graph.builder import get_builder

def main():
    print("=" * 60)
    print("O2C Context Graph System - Initialization Test")
    print("=" * 60)
    
    # Setup paths
    project_dir = os.path.dirname(backend_dir)
    data_dir = os.path.join(project_dir, 'sap-o2c-data')
    db_dir = os.path.join(backend_dir, 'data')
    db_path = os.path.join(db_dir, 'o2c.db')
    
    print(f"\n[1] Paths:")
    print(f"    Project: {project_dir}")
    print(f"    Data: {data_dir}")
    print(f"    Database: {db_path}")
    
    # Verify data directory exists
    if not os.path.exists(data_dir):
        print(f"\n❌ ERROR: Data directory not found: {data_dir}")
        return 1
    
    entity_folders = os.listdir(data_dir)
    print(f"    Found {len(entity_folders)} entity folders")
    
    # Initialize database
    print(f"\n[2] Initializing database...")
    try:
        os.makedirs(db_dir, exist_ok=True)
        db_path = init_database(db_path, data_dir)
        print(f"    ✓ Database initialized at {db_path}")
    except Exception as e:
        print(f"    ❌ ERROR: {e}")
        return 1
    
    # Verify database
    print(f"\n[3] Verifying database...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"    Found {len(tables)} tables:")
        
        for table_name, in tables:
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
            count = cursor.fetchone()[0]
            print(f"      - {table_name}: {count} records")
        
        cursor.execute("PRAGMA table_info('sales_order_headers')")
        columns = cursor.fetchall()
        print(f"\n    Sales Order Headers columns: {len(columns)}")
        for col in columns[:5]:
            print(f"      - {col[1]} ({col[2]})")
        
        conn.close()
        print(f"    ✓ Database verified")
    except Exception as e:
        print(f"    ❌ ERROR: {e}")
        return 1
    
    # Test SQL executor
    print(f"\n[4] Testing SQL executor...")
    try:
        executor = SQLExecutor(db_path)
        schema = executor.get_schema()
        print(f"    Found {len(schema)} tables in schema")
        
        # Get sample data
        sales_order_samples = executor.get_sample_data('sales_order_headers', 2)
        print(f"    Sample sales orders: {len(sales_order_samples)} records")
        if sales_order_samples:
            print(f"      Keys: {list(sales_order_samples[0].keys())[:5]}...")
        
        print(f"    ✓ SQL executor working")
    except Exception as e:
        print(f"    ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Build graph
    print(f"\n[5] Building graph...")
    try:
        builder = get_builder(db_path)
        print(f"    Building NetworkX graph (this will take a minute)...")
        graph = builder.build_graph()
        
        stats = builder.get_graph_stats()
        print(f"    ✓ Graph built:")
        print(f"      - Nodes: {stats['total_nodes']}")
        print(f"      - Edges: {stats['total_edges']}")
        print(f"      - By type: {stats['node_types']}")
        
    except Exception as e:
        print(f"    ❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    print(f"\n" + "=" * 60)
    print("✓ All tests passed! System is ready.")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Set GEMINI_API_KEY environment variable")
    print(f"  2. Run: python main.py")
    print(f"  3. Visit: http://localhost:8000/docs")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
