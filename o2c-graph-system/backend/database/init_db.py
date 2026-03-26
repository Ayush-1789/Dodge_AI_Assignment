"""
Database initialization module - ingests JSONL files and creates SQLite tables.
Dynamically discovers keys in JSONL files, converts camelCase to snake_case,
and creates typed columns.
"""

import json
import sqlite3
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def camel_to_snake(name: str) -> str:
    """Convert camelCase to snake_case."""
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def infer_column_type(value: Any) -> str:
    """Infer SQLite column type from Python value."""
    if value is None:
        return "TEXT"
    elif isinstance(value, bool):
        return "INTEGER"  # SQLite stores booleans as 0/1
    elif isinstance(value, int):
        return "INTEGER"
    elif isinstance(value, float):
        return "REAL"
    elif isinstance(value, dict):
        return "TEXT"  # Store complex objects as JSON strings
    elif isinstance(value, list):
        return "TEXT"  # Store arrays as JSON strings
    else:
        return "TEXT"


def scan_jsonl_file(file_path: str, sample_size: int = 100) -> Dict[str, str]:
    """
    Scan a JSONL file to discover column names and infer types.
    
    Args:
        file_path: Path to JSONL file
        sample_size: Number of records to scan for type inference
    
    Returns:
        Dictionary mapping column names (snake_case) to inferred SQLite types
    """
    column_types = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= sample_size:
                    break
                
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    for key, value in record.items():
                        snake_key = camel_to_snake(key)
                        
                        if snake_key not in column_types:
                            column_types[snake_key] = infer_column_type(value)
                        else:
                            # Upgrade type if needed (TEXT is most general)
                            current_type = column_types[snake_key]
                            new_type = infer_column_type(value)
                            if new_type == "TEXT" and current_type != "TEXT":
                                column_types[snake_key] = "TEXT"
                
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON decode error in {file_path} line {i+1}: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Error scanning {file_path}: {e}")
    
    return column_types


def get_primary_key(table_name: str, columns: Dict[str, str]) -> str:
    """
    Determine the primary key for a table based on naming conventions.
    Priority: id, {table}_id, _id, or first column if no id found.
    """
    # Remove trailing 's' for plural to singular matching
    singular = table_name.rstrip('s')
    
    candidates = [
        f"{singular}_id",
        "id",
        f"{table_name}_id",
    ]
    
    for candidate in candidates:
        if candidate in columns:
            return candidate
    
    # If no ID column found, use first column
    return list(columns.keys())[0] if columns else "id"


def create_tables(db_path: str, data_dir: str) -> Dict[str, List[str]]:
    """
    Dynamically create SQLite tables from JSONL files.
    
    Args:
        db_path: Path to SQLite database file
        data_dir: Path to directory containing JSONL subdirectories
    
    Returns:
        Dictionary mapping table names to their created columns
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    table_info = {}
    
    # Scan data directory for entity folders
    for entity_folder in os.listdir(data_dir):
        entity_path = os.path.join(data_dir, entity_folder)
        
        if not os.path.isdir(entity_path):
            continue
        
        table_name = entity_folder
        logger.info(f"Processing entity: {table_name}")
        
        # Discover all columns in this entity
        all_columns = {}
        
        for jsonl_file in os.listdir(entity_path):
            if not jsonl_file.endswith('.jsonl'):
                continue
            
            file_path = os.path.join(entity_path, jsonl_file)
            file_columns = scan_jsonl_file(file_path)
            
            # Merge columns (union of all found columns)
            for col_name, col_type in file_columns.items():
                if col_name not in all_columns:
                    all_columns[col_name] = col_type
        
        if not all_columns:
            logger.warning(f"No columns found for {table_name}")
            continue
        
        # Build CREATE TABLE statement
        columns_sql = []
        for col_name in sorted(all_columns.keys()):
            col_type = all_columns[col_name]
            columns_sql.append(f'"{col_name}" {col_type}')
        
        # Add raw_json column to store original records
        columns_sql.append('"raw_json" TEXT')
        
        create_statement = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            {','.join(columns_sql)}
        )
        """
        
        try:
            cursor.execute(create_statement)
            logger.info(f"Created table: {table_name} with {len(all_columns)} columns")
            table_info[table_name] = sorted(all_columns.keys())
        except sqlite3.Error as e:
            logger.error(f"Error creating table {table_name}: {e}")
            logger.error(f"SQL: {create_statement}")
        
        conn.commit()
    
    conn.close()
    return table_info


def ingest_jsonl_files(db_path: str, data_dir: str) -> Dict[str, int]:
    """
    Ingest JSONL files into SQLite tables.
    
    Args:
        db_path: Path to SQLite database file
        data_dir: Path to directory containing JSONL subdirectories
    
    Returns:
        Dictionary mapping table names to row counts inserted
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    insert_counts = {}
    
    # Get existing tables from database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    for entity_folder in os.listdir(data_dir):
        entity_path = os.path.join(data_dir, entity_folder)
        
        if not os.path.isdir(entity_path) or entity_folder not in existing_tables:
            continue
        
        table_name = entity_folder
        insert_count = 0
        
        logger.info(f"Ingesting data for: {table_name}")
        
        # Get column info for this table
        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info if col[1] != 'raw_json']
        
        # Process JSONL files
        for jsonl_file in os.listdir(entity_path):
            if not jsonl_file.endswith('.jsonl'):
                continue
            
            file_path = os.path.join(entity_path, jsonl_file)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if not line.strip():
                            continue
                        
                        try:
                            record = json.loads(line)
                            
                            # Convert keys to snake_case and extract values
                            row_data = {}
                            for original_key, value in record.items():
                                snake_key = camel_to_snake(original_key)
                                if snake_key in columns:
                                    # Convert complex types to JSON strings
                                    if isinstance(value, (dict, list)):
                                        row_data[snake_key] = json.dumps(value)
                                    else:
                                        row_data[snake_key] = value
                            
                            # Add raw JSON
                            row_data['raw_json'] = json.dumps(record)
                            
                            # Insert row
                            placeholders = ','.join(['?' for _ in range(len(columns) + 1)])
                            col_names = ','.join([f'"{c}"' for c in columns] + ['"raw_json"'])
                            
                            insert_sql = f"""
                            INSERT INTO "{table_name}" ({col_names})
                            VALUES ({placeholders})
                            """
                            
                            values = [row_data.get(c) for c in columns] + [row_data['raw_json']]
                            cursor.execute(insert_sql, values)
                            insert_count += 1
                        
                        except json.JSONDecodeError as e:
                            logger.debug(f"JSON decode error: {e}")
                            continue
                
                conn.commit()
                
            except Exception as e:
                logger.error(f"Error ingesting {file_path}: {e}")
                continue
        
        insert_counts[table_name] = insert_count
        logger.info(f"Inserted {insert_count} records into {table_name}")
    
    conn.close()
    return insert_counts


def init_database(db_path: str = None, data_dir: str = None) -> str:
    """
    Initialize the SQLite database with JSONL data.
    
    Args:
        db_path: Path to database (defaults to ./data/o2c.db)
        data_dir: Path to JSONL data directory (defaults to ../../../sap-o2c-data)
    
    Returns:
        Path to created database
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'o2c.db')
    
    if data_dir is None:
        # Look for sap-o2c-data in parent directories
        current_dir = os.path.dirname(__file__)
        for _ in range(4):  # Go up to 4 levels
            test_path = os.path.join(current_dir, 'sap-o2c-data')
            if os.path.isdir(test_path):
                data_dir = test_path
                break
            current_dir = os.path.dirname(current_dir)
    
    if data_dir is None:
        raise ValueError("Could not locate sap-o2c-data directory")
    
    # Create data directory if it doesn't exist
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    # Remove existing database to start fresh
    if os.path.exists(db_path):
        os.remove(db_path)
    
    logger.info(f"Creating database at: {db_path}")
    logger.info(f"Data directory: {data_dir}")
    
    # Create tables
    table_info = create_tables(db_path, data_dir)
    logger.info(f"Created {len(table_info)} tables")
    
    # Ingest data
    insert_counts = ingest_jsonl_files(db_path, data_dir)
    logger.info(f"Ingestion complete: {sum(insert_counts.values())} total records")
    
    # Verify database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    logger.info(f"\nDatabase contains {len(tables)} tables:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM \"{table[0]}\"")
        count = cursor.fetchone()[0]
        logger.info(f"  - {table[0]}: {count} records")
    
    conn.close()
    
    return db_path


if __name__ == '__main__':
    db_path = init_database()
    print(f"\nDatabase initialized at: {db_path}")
