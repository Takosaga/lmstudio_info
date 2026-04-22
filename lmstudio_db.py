"""Database layer for LMStudio conversation storage."""
import sqlite3
import os
import time
from datetime import datetime
from contextlib import contextmanager


@contextmanager
def get_connection(db_path):
    """Context manager for SQLite connections with retry logic
    
    Args:
        db_path: Path to the SQLite database file
        
    Yields:
        sqlite3.Connection object
    """
    conn = None
    try:
        # SQLite will create the file automatically if it doesn't exist
        max_retries = 3
        base_delay = 0.1
        
        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(db_path)
                yield conn
                break
            except sqlite3.Error as e:
                if attempt == max_retries - 1:
                    raise ConnectionError(f"Failed to connect after {max_retries} attempts") from e
                time.sleep(base_delay * (2 ** attempt))
    finally:
        if conn:
            conn.close()


def init_db(db_path):
    """Initialize database and create conversations table
    
    Creates the 'conversations' table with columns for:
    - filename (TEXT PRIMARY KEY): Unique identifier
    - token_count (INTEGER): Total conversation tokens
    - message_count (INTEGER): Number of messages
    - model (TEXT): Model used for conversation
    - created_at (TIMESTAMP): Timestamp when conversation was created
    - user_last_message_at (TIMESTAMP): Last user interaction timestamp
    
    Args:
        db_path: Path to the SQLite database file
    """
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Create conversations table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                filename TEXT PRIMARY KEY,
                token_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                model TEXT DEFAULT '',
                created_at TIMESTAMP,
                user_last_message_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')
        
        conn.commit()


def check_record_exists(cursor, filename):
    """Check if a record with given filename exists
    
    Args:
        cursor: SQLite database cursor
        filename: Filename of the conversation to check
        
    Returns:
        bool: True if record exists, False otherwise
    """
    cursor.execute(
        "SELECT 1 FROM conversations WHERE filename = ? LIMIT 1",
        (filename,)
    )
    return cursor.fetchone() is not None


def get_or_create_table(conn):
    """Ensure conversations table exists
    
    Args:
        conn: SQLite database connection
    """
    cursor = conn.cursor()
    
    # Check if table exists first to avoid re-creating it constantly
    cursor.execute('''
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='conversations'
    ''')
    
    is_created = cursor.fetchone() is not None
    
    if not is_created:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                filename TEXT PRIMARY KEY,
                token_count INTEGER DEFAULT 0,
                message_count INTEGER DEFAULT 0,
                model TEXT DEFAULT '',
                created_at TIMESTAMP,
                user_last_message_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        ''')


def upsert_conversation(db_path, conversation_data):
    """Upsert a conversation record into the database
    
    Inserts a new record if filename doesn't exist, 
    or updates existing record if data has changed.
    
    Args:
        db_path: Path to the SQLite database file
        conversation_data: Dict containing conversation metadata:
            - filename: Unique identifier for the conversation
            - token_count: Total tokens in conversation
            - message_count: Number of messages
            - model: Model used
            - created_at: Creation timestamp
            - user_last_message_at: Last user message timestamp
    
    Returns:
        bool: True if record was inserted, False if updated
    """
    filename = conversation_data.get('filename')
    
    if not filename:
        raise ValueError("Filename is required")
    
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Create table if needed
        get_or_create_table(conn)
        
        current_time = datetime.now().isoformat()
        
        if check_record_exists(cursor, filename):
            # Check if data has actually changed
            cursor.execute(
                """
                    SELECT token_count, message_count, model 
                    FROM conversations WHERE filename = ?
                """,
                (filename,)
            )
            existing = cursor.fetchone()
            
            new_token_count = conversation_data.get('token_count', 0)
            new_message_count = conversation_data.get('message_count', 0)
            
            if existing and new_token_count == existing[0] and new_message_count == existing[1]:
                # No significant change, skip update
                return False
            
            # Update fields that may have changed
            updated_fields = []
            if conversation_data.get('token_count') != existing or existing is None:
                updated_fields.append(f"token_count = ?")
                sql_params = [conversation_data.get('token_count', 0)]
            else:
                sql_params = existing[:1] + [new_token_count]
            
            if conversation_data.get('message_count') != existing or existing is None:
                updated_fields.append(f"message_count = ?")
                sql_params.extend([conversation_data.get('message_count', 0)])
            else:
                sql_params.extend(existing[1:])
            
            if conversation_data.get('model') and conversation_data.get('model') != (existing[2] if existing else ''):
                updated_fields.append("model = ?")
                sql_params.append(conversation_data.get('model'))
            
            # Set timestamps on update
            updated_fields.append(f"updated_at = ?")
            sql_params.append(current_time)
            
            # Add remaining fields
            for key, value in conversation_data.items():
                if key not in ['filename', 'token_count', 'message_count', 'model']:
                    field = f"{key} = ?"
                    updated_fields.append(field)
                    sql_params.append(value)
            
            upsert_query = f"""
                UPDATE conversations 
                SET {', '.join(updated_fields)}
                WHERE filename = ?
            """
            
            cursor.execute(upsert_query, sql_params + [filename])
            conn.commit()
        
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO conversations (
                    filename, token_count, message_count, model,
                    created_at, user_last_message_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename,
                conversation_data.get('token_count', 0),
                conversation_data.get('message_count', 0),
                conversation_data.get('model', ''),
                conversation_data.get('created_at'),
                conversation_data.get('user_last_message_at', None),
                current_time
            ))
            conn.commit()


def get_usage_by_model(db_path):
    """Get total token usage grouped by model
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        List of tuples (model, total_tokens) sorted by tokens descending
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT model, SUM(token_count) as total_tokens 
            FROM conversations 
            WHERE model IS NOT NULL AND model != ''
            GROUP BY model 
            ORDER BY total_tokens DESC
        ''')
        return cursor.fetchall()


def get_total_usage(db_path):
    """Get total token usage across all conversations
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        int: Total token count
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT SUM(token_count) FROM conversations')
        result = cursor.fetchone()[0]
        return result or 0


def get_conversations_by_date_range(db_path, start_date=None, end_date=None):
    """Get conversations within a date range
    
    Args:
        db_path: Path to the SQLite database file
        start_date: Start date as ISO string (optional)
        end_date: End date as ISO string (optional)
        
    Returns:
        List of conversation records from within the date range
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        query = "SELECT * FROM conversations WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND created_at >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND created_at <= ?"
            params.append(end_date)
        
        cursor.execute(query, params)
        return cursor.fetchall()
