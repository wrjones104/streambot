import sqlite3
import os

DATABASE_NAME = 'bot_config.db'

def connect_db():
    """Connects to the SQLite database."""
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def get_config(category: str, key: str):
    """Retrieves a configuration value from the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE category = ? AND key = ?", (category, key))
    result = cursor.fetchone()
    conn.close()
    return result['value'] if result else None

def save_config(category: str, key: str, value: str):
    """Saves or updates a configuration value in the database."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE category = ? AND key = ?", (category, key))
    existing = cursor.fetchone()
    if existing:
        cursor.execute("UPDATE config SET value = ? WHERE category = ? AND key = ?", (value, category, key))
    else:
        cursor.execute("INSERT INTO config (category, key, value) VALUES (?, ?, ?)", (category, key, value))
    conn.commit()
    conn.close()

def get_all_config(category: str):
    """Retrieves all configuration items for a given category."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM config WHERE category = ?", (category,))
    results = cursor.fetchall()
    conn.close()
    return {row['key']: row['value'] for row in results}

def initialize_db():
    """Initializes the database and creates the config table if it doesn't exist,
    prompting for essential credentials if they are not found.
    """
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        )
    """)
    conn.commit()

    credentials_to_check = {
        'discord_token': 'Your Discord Bot Token',
        'twitch_client_id': 'Your Twitch Client ID',
        'twitch_client_secret': 'Your Twitch Client Secret'
    }

    for key, prompt in credentials_to_check.items():
        if not get_config('credentials', key):
            value = input(f"Please enter {prompt}: ").strip()
            save_config('credentials', key, value)
            print(f"{key} has been saved to the database.")

    conn.close()

# Initialize the database when this module is imported
initialize_db()