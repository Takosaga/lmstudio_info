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
                updated_at TIMESTAMP,
                source TEXT DEFAULT 'lmstudio',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0
            )
        ''')

        # Schema migration: add new columns if table existed without them
        cursor.execute("PRAGMA table_info(conversations)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        new_columns = [
            ('source', "TEXT DEFAULT 'lmstudio'"),
            ('input_tokens', 'INTEGER DEFAULT 0'),
            ('output_tokens', 'INTEGER DEFAULT 0'),
            ('reasoning_tokens', 'INTEGER DEFAULT 0'),
            ('cache_read_tokens', 'INTEGER DEFAULT 0'),
            ('cache_write_tokens', 'INTEGER DEFAULT 0'),
            ('tool_call_count', 'INTEGER DEFAULT 0'),
        ]
        for col_name, col_def in new_columns:
            if col_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE conversations ADD COLUMN {col_name} {col_def}"
                )

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
                updated_at TIMESTAMP,
                source TEXT DEFAULT 'lmstudio',
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                reasoning_tokens INTEGER DEFAULT 0,
                cache_read_tokens INTEGER DEFAULT 0,
                cache_write_tokens INTEGER DEFAULT 0,
                tool_call_count INTEGER DEFAULT 0
            )
        ''')

    # Schema migration: add new columns if table existed without them
    cursor.execute("PRAGMA table_info(conversations)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    new_columns = [
        ('source', "TEXT DEFAULT 'lmstudio'"),
        ('input_tokens', 'INTEGER DEFAULT 0'),
        ('output_tokens', 'INTEGER DEFAULT 0'),
        ('reasoning_tokens', 'INTEGER DEFAULT 0'),
        ('cache_read_tokens', 'INTEGER DEFAULT 0'),
        ('cache_write_tokens', 'INTEGER DEFAULT 0'),
        ('tool_call_count', 'INTEGER DEFAULT 0'),
    ]
    for col_name, col_def in new_columns:
        if col_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE conversations ADD COLUMN {col_name} {col_def}"
            )


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
                    SELECT token_count, message_count, model, source,
                           input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, tool_call_count
                    FROM conversations WHERE filename = ?
                """,
                (filename,)
            )
            existing = cursor.fetchone()

            new_token_count = conversation_data.get('token_count', 0)
            new_message_count = conversation_data.get('message_count', 0)
            new_input_tokens = conversation_data.get('input_tokens', 0)
            new_output_tokens = conversation_data.get('output_tokens', 0)
            new_reasoning_tokens = conversation_data.get('reasoning_tokens', 0)
            new_cache_read_tokens = conversation_data.get('cache_read_tokens', 0)
            new_tool_call_count = conversation_data.get('tool_call_count', 0)

            existing_source = existing[3] if existing else None
            existing_input = existing[4] if existing else None
            existing_output = existing[5] if existing else None
            existing_reasoning = existing[6] if existing else None
            existing_cache = existing[7] if existing else None
            existing_tool_call = existing[8] if existing else None

            new_model = conversation_data.get('model', '')
            if (existing and new_token_count == existing[0]
                    and new_message_count == existing[1]
                    and new_model == (existing[2] if existing else '')
                    and new_input_tokens == existing_input
                    and new_output_tokens == existing_output
                    and new_reasoning_tokens == existing_reasoning
                    and new_cache_read_tokens == existing_cache
                    and new_tool_call_count == existing_tool_call):
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
                    created_at, user_last_message_at, updated_at,
                    source, input_tokens, output_tokens, reasoning_tokens, cache_read_tokens, cache_write_tokens, tool_call_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                filename,
                conversation_data.get('token_count', 0),
                conversation_data.get('message_count', 0),
                conversation_data.get('model', ''),
                conversation_data.get('created_at'),
                conversation_data.get('user_last_message_at', None),
                current_time,
                conversation_data.get('source', 'lmstudio'),
                conversation_data.get('input_tokens', 0),
                conversation_data.get('output_tokens', 0),
                conversation_data.get('reasoning_tokens', 0),
                conversation_data.get('cache_read_tokens', 0),
                conversation_data.get('cache_write_tokens', 0),
                conversation_data.get('tool_call_count', 0),
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
