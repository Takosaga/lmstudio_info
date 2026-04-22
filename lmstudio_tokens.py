import json
import glob
import os
from pathlib import Path
from datetime import datetime, timezone


def scan_conversations():
    """Find all conversation JSON files in LMStudio conversations directory"""
    conversations_dir = os.path.expanduser('~/.lmstudio/conversations')

    if not os.path.exists(conversations_dir) or not os.path.isdir(conversations_dir):
        return []

    try:
        json_files = glob.glob(os.path.join(conversations_dir, '*.json'))
        if isinstance(json_files, list):
            return sorted([str(Path(f).resolve()) for f in json_files])
        return []
    except Exception:
        return []


def extract_from_json(file_path):
    """Parse LMStudio JSON and extract metadata"""
    with open(file_path, 'r', encoding='utf-8') as f:
        chat_data = json.load(f)

    # Extract fields with defaults
    total_tokens_raw = chat_data.get('tokenCount')
    messages_list = chat_data.get('messages', []) if isinstance(chat_data, dict) else []
    last_used_model = chat_data.get('lastUsedModel')
    model_name = last_used_model.get('identifier', '') if isinstance(last_used_model, dict) else last_used_model or ''
    created_at_ts = chat_data.get('createdAt')
    user_last_message_at_ts = chat_data.get('userLastMessagedAt')

    # Handle token count - convert to int and default to 0 for falsy values
    try:
        if total_tokens_raw is None:
            total_tokens = 0
        else:
            total_tokens = int(float(total_tokens_raw))
    except (ValueError, TypeError):
        total_tokens = 0

    # Handle message count
    message_count = len(messages_list) if isinstance(messages_list, list) else 0

    # Handle timestamps - convert to datetime or None
    # Check if timestamp is milliseconds (>4 digits after 1970 epoch) or seconds
    def parse_timestamp(ts_val):
        """Parse timestamp, handling both seconds and milliseconds"""
        try:
            # If ts > year 2100 (in seconds), it's likely milliseconds
            if ts_val > 3999999999:
                return datetime.fromtimestamp(ts_val / 1000, tz=timezone.utc).replace(tzinfo=None)
            elif ts_val > 2555040000:  # ~year 2100 in seconds
                return datetime.fromtimestamp(ts_val, tz=timezone.utc).replace(tzinfo=None)
            else:
                return datetime.fromtimestamp(ts_val / 1000, tz=timezone.utc).replace(tzinfo=None)
        except (ValueError, OSError):
            return None
    
    created_at = None
    if created_at_ts is not None:
        try:
            created_at = parse_timestamp(created_at_ts)
        except (ValueError, OSError):
            created_at = None

    user_last_message_at = None
    if user_last_message_at_ts is not None:
        try:
            user_last_message_at = parse_timestamp(user_last_message_at_ts)
        except (ValueError, OSError):
            user_last_message_at = None

    return {
        'filename': Path(file_path).name,
        'token_count': total_tokens,
        'message_count': message_count,
        'model': model_name,
        'created_at': created_at,
        'user_last_message_at': user_last_message_at,
    }


def load_conversations_from_files(json_files):
    """Load conversations from list of JSON file paths"""
    conversations = []
    for json_file in json_files:
        try:
            conv_data = extract_from_json(json_file)
            conversations.append(conv_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load {json_file}: {e}")
    return conversations


def main():
    """Main entry point for command-line usage"""
    json_files = scan_conversations()
    print(f"Found {len(json_files)} conversation file(s)")
    
    if json_files:
        print("\nParsing conversations...")
        conversations = load_conversations_from_files(json_files)
        print(f"Successfully extracted {len(conversations)} conversation(s)\n")
        
        # Print summary for first conversation
        if conversations:
            print("Example data:")
            conv = conversations[0]
            print(f"  File: {conv['filename']}")
            print(f"  Tokens: {conv['token_count']}")
            print(f"  Messages: {conv['message_count']}")
            print(f"  Model: {conv['model']}")
            if conv['created_at']:
                print(f"  Created at: {conv['created_at'].isoformat()}")
