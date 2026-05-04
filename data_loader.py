"""Data loader module for Notebook interface."""
import os
import pandas as pd
from contextlib import contextmanager
import sqlite3

from lmstudio_db import get_connection


@contextmanager
def data_get_connection(db_path):
    """Get database connection for data loading
    
    This wrapper uses the database connection helper with proper error handling.
    
    Args:
        db_path: Path to the SQLite database file
        
    Yields:
        sqlite3.Connection object
        
    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    conn = None
    try:
        from lmstudio_db import get_connection as db_get_connection
        
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Database file not found at {db_path}")
        
        yield db_get_connection(db_path)
    
    except ImportError:
        # Fallback basic connection
        conn = sqlite3.connect(db_path)
        try:
            yield conn
        finally:
            if conn:
                conn.close()


def load_usage_data(db_path=None, start_date=None, end_date=None):
    """Load all conversation data into a pandas DataFrame
    
    Reads from the database and creates a DataFrame with columns:
    - filename: Conversation file identifier
    - token_count: Total tokens in conversation
    - message_count: Number of messages
    - model: Model used
    - created_at: Creation timestamp
    - user_last_message_at: Last user message timestamp
    
    Args:
        db_path: Path to SQLite database (if None, uses default location)
        start_date: Filter conversations from this date (ISO format: 'YYYY-MM-DD')
        end_date: Filter conversations until this date (ISO format: 'YYYY-MM-DD')
        
    Returns:
        pandas.DataFrame with conversation data
        
    Raises:
        FileNotFoundError: If database doesn't exist or has no data
    """
    import os
    from pathlib import Path
    
    if db_path is None:
        # Default to a standard location
        default_db = Path.home() / '.lmstudio' / 'usage.db'
        if not default_db.exists():
            raise FileNotFoundError(f"Default database not found at {default_db}")
        db_path = default_db
    
    conn = sqlite3.connect(db_path)
    
    try:
        # Build query with optional date filters
        query = """
            SELECT 
                filename,
                token_count,
                message_count,
                model,
                created_at,
                user_last_message_at,
                updated_at
            FROM conversations
        """
        params = []
        
        if start_date or end_date:
            query += " WHERE"
            if start_date:
                query += " created_at >= ?"
                params.append(start_date)
            if end_date:
                if start_date:
                    query += " AND"
                query += " created_at <= ?"
                params.append(end_date)
        
        query += " ORDER BY created_at NULLS LAST"
        
        df = pd.read_sql_query(query, conn, params=params if params else None, parse_dates=["created_at"])
        
        if df.empty:
            raise FileNotFoundError(f"Database exists but is empty at {db_path}")
            
        return df
        
    except sqlite3.OperationalError as e:
        # Re-raise specific errors like missing table as FileNotFoundError
        if "no such table" in str(e).lower():
            raise FileNotFoundError(f"No 'conversations' table found in database at {db_path}")
        raise
    finally:
        conn.close()


def get_connection(db_path):
    """Get a database connection
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        sqlite3.Connection object
        
    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at {db_path}")
    
    conn = sqlite3.connect(db_path)
    return conn


def load_conversations_by_model(db_path, model=None):
    """Load conversations filtered by model
    
    Args:
        db_path: Path to SQLite database
        model: If provided, only load conversations for this model
        
    Returns:
        pandas.DataFrame with filtered results
    """
    import os
    import pandas as pd
    import sqlite3
    
    conn = sqlite3.connect(db_path)
    
    try:
        if model:
            query = f"SELECT * FROM conversations WHERE model = ?"
            params = (model,)
        else:
            query = "SELECT * FROM conversations"
            params = ()
        
        df = pd.read_sql_query(query, conn, params=params)
        return df
        
    finally:
        conn.close()


def get_token_statistics(db_path=None):
    """Get aggregated statistics about token usage
    
    Args:
        db_path: Path to SQLite database (uses default if None)
        
    Returns:
        dict with statistical aggregates
    """
    import os
    import pandas as pd
    from lmstudio_db import get_connection as db_get_connection
    
    conn = None
    
    try:
        if db_path is None:
            raise FileNotFoundError("Database path required for statistics")
        
        conn = sqlite3.connect(db_path)
        
        # Get total token usage
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(token_count) FROM conversations")
        total_tokens = cursor.fetchone()[0] or 0
        
        # Get average tokens per conversation
        cursor.execute("SELECT AVG(token_count), COUNT(*) FROM conversations")
        avg_tokens, count = cursor.fetchone()
        
        return {
            'total_tokens': total_tokens,
            'conversation_count': count if count else 0,
            'avg_tokens_per_conv': avg_tokens if avg_tokens is not None else 0
        }
        
    finally:
        if conn:
            conn.close()
