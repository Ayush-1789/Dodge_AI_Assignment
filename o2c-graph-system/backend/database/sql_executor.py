"""
SQL execution layer - safe SQL executor for read-only queries on O2C database.
Validates queries against SQL injection patterns and executes safely.
"""

import sqlite3
import re
import logging
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

# SQL injection prevention patterns
BLOCKED_SQL_PATTERNS = [
    r'\bDROP\b',
    r'\bDELETE\b',
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bALTER\b',
    r'\bCREATE\b',
    r'--',
    r';.*;'
]


def is_safe_sql(sql: str) -> Tuple[bool, str]:
    """
    Validate SQL query for safety (read-only, no injection patterns).
    
    Args:
        sql: SQL query to validate
    
    Returns:
        Tuple of (is_safe: bool, reason: str)
    """
    sql_upper = sql.upper().strip()
    
    # Must start with SELECT
    if not sql_upper.startswith('SELECT'):
        return False, "Only SELECT queries are allowed"
    
    # Check for blocked patterns
    for pattern in BLOCKED_SQL_PATTERNS:
        if re.search(pattern, sql, re.IGNORECASE):
            return False, f"Query contains blocked SQL pattern: {pattern}"
    
    return True, "Query is safe"


class SQLExecutor:
    """Safe SQL executor for O2C database queries."""
    
    def __init__(self, db_path: str):
        """Initialize with path to SQLite database."""
        self.db_path = db_path
    
    def execute(self, sql: str, params: List = None) -> List[Dict[str, Any]]:
        """
        Execute a safe SELECT query against the database.
        
        Args:
            sql: SELECT query (will be validated)
            params: Optional query parameters (for parameterized queries)
        
        Returns:
            List of result rows as dictionaries
        """
        # Validate query
        is_safe, reason = is_safe_sql(sql)
        if not is_safe:
            raise ValueError(f"Query blocked for safety: {reason}")
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Return rows as dicts
            cursor = conn.cursor()
            
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            results = []
            for row in cursor.fetchall():
                results.append(dict(row))
            
            conn.close()
            return results
        
        except sqlite3.Error as e:
            logger.error(f"Database error: {e}")
            raise
    
    def execute_count(self, sql: str, params: List = None) -> int:
        """Execute query and return row count."""
        results = self.execute(sql, params)
        return len(results)
    
    def get_schema(self) -> Dict[str, List[str]]:
        """
        Get database schema (table names and columns).
        
        Returns:
            Dictionary mapping table names to column lists
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            schema = {}
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table_name, in tables:
                cursor.execute(f'PRAGMA table_info("{table_name}")')
                columns = [col[1] for col in cursor.fetchall()]
                schema[table_name] = columns
            
            conn.close()
            return schema
        
        except sqlite3.Error as e:
            logger.error(f"Error getting schema: {e}")
            raise
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample rows from a table."""
        sql = f'SELECT * FROM "{table_name}" LIMIT ?'
        return self.execute(sql, [limit])
