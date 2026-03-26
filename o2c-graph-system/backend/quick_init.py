#!/usr/bin/env python
"""
Quick initialization for O2C context graph system
"""
import sys
import os

# Absolute path to data
DATA_DIR = "f:\\Assignment 2\\sap-o2c-data"
DB_PATH = "f:\\Assignment 2\\o2c-graph-system\\backend\\data\\o2c.db"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

print("Initializing O2C Database...")
print(f"Data: {DATA_DIR}")
print(f"Database: {DB_PATH}")

# Change to backend directory for imports
os.chdir("f:\\Assignment 2\\o2c-graph-system\\backend")
sys.path.insert(0, os.getcwd())

from database.init_db import init_database

try:
    print("\n[Step 1] Creating database and tables...")
    init_database(DB_PATH, DATA_DIR)
    print("✓ Database initialization complete\n")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Verify
print("[Step 2] Verifying database...")
try:
    from database.sql_executor import SQLExecutor
    executor = SQLExecutor(DB_PATH)
    schema = executor.get_schema()
    print(f"✓ Database verified: {len(schema)} tables found\n")
except Exception as e:
    print(f"✗ Error: {e}")
    sys.exit(1)

print("=" * 60)
print("Database is ready! You can now run the backend with:")
print("  cd f:\\Assignment 2\\o2c-graph-system\\backend")  
print("  python main.py")
print("=" * 60)
