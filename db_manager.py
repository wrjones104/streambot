import aiosqlite
import sqlite3

DATABASE_NAME = 'bot_config.db'

async def connect_db():
    """Connects to the SQLite database asynchronously."""
    conn = await aiosqlite.connect(DATABASE_NAME)
    conn.row_factory = aiosqlite.Row  # This allows accessing columns by name
    return conn

async def get_config(conn: aiosqlite.Connection, category: str, key: str):
    """Retrieves a configuration value from the database."""
    async with conn.execute("SELECT value FROM config WHERE category = ? AND key = ?", (category, key)) as cursor:
        result = await cursor.fetchone()
        return result['value'] if result else None

async def save_config(conn: aiosqlite.Connection, category: str, key: str, value: str):
    """Saves or updates a configuration value in the database."""
    cursor = await conn.execute("SELECT value FROM config WHERE category = ? AND key = ?", (category, key))
    existing = await cursor.fetchone()
    if existing:
        await conn.execute("UPDATE config SET value = ? WHERE category = ? AND key = ?", (value, category, key))
    else:
        await conn.execute("INSERT INTO config (category, key, value) VALUES (?, ?, ?)", (category, key, value))
    await conn.commit()

async def get_all_config(conn: aiosqlite.Connection, category: str):
    """Retrieves all configuration items for a given category."""
    async with conn.execute("SELECT key, value FROM config WHERE category = ?", (category,)) as cursor:
        results = await cursor.fetchall()
        return {row['key']: row['value'] for row in results}

async def remove_config(conn: aiosqlite.Connection, category: str, key: str):
    """Removes a configuration value from the database."""
    cursor = await conn.execute("DELETE FROM config WHERE category = ? AND key = ?", (category, key))
    await conn.commit()
    return cursor.rowcount > 0

def initialize_db():
    """Initializes the database and creates the config table if it doesn't exist,
    prompting for essential credentials if they are not found.
    This function remains synchronous as it's part of the initial setup.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT UNIQUE NOT NULL,
            value TEXT NOT NULL
        )
    """)
    # Check for unique constraint on category and key together
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_category_key ON config (category, key)")
    conn.commit()

    # Synchronous get_config for initialization
    def get_config_sync(cat, k):
        cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE category = ? AND key = ?", (cat, k))
        res = cur.fetchone()
        return res['value'] if res else None

    # Synchronous save_config for initialization
    def save_config_sync(cat, k, val):
        cur = conn.cursor()
        cur.execute("SELECT value FROM config WHERE category = ? AND key = ?", (cat, k))
        if cur.fetchone():
            cur.execute("UPDATE config SET value = ? WHERE category = ? AND key = ?", (val, cat, k))
        else:
            cur.execute("INSERT INTO config (category, key, value) VALUES (?, ?, ?)", (cat, k, val))
        conn.commit()

    credentials_to_check = {
        'discord_token': 'Your Discord Bot Token',
        'twitch_client_id': 'Your Twitch Client ID',
        'twitch_client_secret': 'Your Twitch Client Secret'
    }

    for key, prompt in credentials_to_check.items():
        if not get_config_sync('credentials', key):
            value = input(f"Please enter {prompt}: ").strip()
            save_config_sync('credentials', key, value)
            print(f"{key} has been saved to the database.")

    conn.close()

# Initialize the database when this module is imported
initialize_db()