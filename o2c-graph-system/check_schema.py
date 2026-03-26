#!/usr/bin/env python3
"""Check database schema."""

import sqlite3
from pathlib import Path

db_path = Path('backend/data/o2c.db')
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print('\n=== DATABASE SCHEMA ===\n')
    for (table_name,) in tables:
        print(f'TABLE: {table_name}')
        cursor.execute(f'PRAGMA table_info({table_name})')
        columns = cursor.fetchall()
        for cid, name, type_, notnull, dflt_value, pk in columns:
            pk_marker = ' [PK]' if pk else ''
            print(f'  - {name}: {type_}{pk_marker}')
        print()
    
    conn.close()
else:
    print('Database does not exist yet')
