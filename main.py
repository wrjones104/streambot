import asyncio
import datetime
import calendar
import json
import os
import sys
import logging
from sqlite3 import connect

import discord
from discord.ext import tasks, commands
from discord.utils import get
from discord import app_commands

import db_manager
from twitch_api import TwitchAPI
from views import streamButton

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_sync_db_connection():
    """Gets a synchronous connection for startup tasks."""
    conn = connect(db_manager.DATABASE_NAME)
    conn.row_factory = lambda cursor, row: row[0]
    return conn

def check_admin(interaction: discord.Interaction):
    """Checks if the user has one of the admin roles."""
    # This could be improved by storing role IDs in the database instead of hardcoding names
    admin_roles = {"Racebot Admin", "Moderation team", "Admins"}
    return any(role.name in admin_roles for role in interaction.user.roles)

def restart_bot():
    """Restarts the bot.
    Note: This is a hard restart and will lose all in-memory state.
    """
    os.execv(sys.executable, ['python3'] + sys.argv)

async def get_category_config(interaction: discord.Interaction, category_id: str):
    """A helper to get and decode a category's config."""
    config_json = await db_manager.get_config(interaction.client.db_conn, 'game_categories', category_id)
    if not config_json:
        await interaction.response.send_message(f"Category ID '{category_id}' not found.", ephemeral=True)
        return None
    try:
        return json.loads(config_json)
    except json.JSONDecodeError:
        await interaction.response.send_message(f"Error decoding configuration for category ID '{category_id}'.", ephemeral=True)
        return None

class StreamBot(commands.Bot):
    def __init__(self, *, intents: discord.Intents, **options):
        super().__init__(command_prefix='%^!', intents=intents, **options)
        self.db_conn = None
        self.twitch_api = None
        self.current_stream_msgs = {}  # In-memory cache of posted stream messages

    async def setup_hook(self) -> None:
        # --- Database Connection ---
        self.db_conn = await db_manager.connect_db()
        logging.info("Database connection established.")

        # --- Twitch API Client ---
        client_id = await db_manager.get_config(self.db_conn, 'credentials', 'twitch_client_id')
        client_secret = await db_manager.get_config(self.db_conn, 'credentials', 'twitch_client_secret')
        if not all([client_id, client_secret]):
            logging.error("Twitch client ID or secret not found in database. Bot cannot start.")
            return

        self.twitch_api = TwitchAPI(client_id, client_secret, self.db_conn)
        logging.info("Twitch API client initialized.")

        # --- Sync slash commands ---
        synclist = await self.tree.sync()
        logging.info(f"Slash Commands Synced: {len(synclist)}")

        # --- Start background task ---
        self.get_streams_task.start()

    async def on_ready(self):
        logging.info(f"Logged in as {self.user.name} (ID: {self.user.id})")
        logging.info(f"discord.py version: {discord.__version__}")

    async def close(self):
        logging.info("Closing connections...")
        if self.twitch_api:
            await self.twitch_api.close()
        if self.db_conn:
            await self.db_conn.close()
        await super().close()

    async def purge_and_notify_channels(self):
        """Purges old messages from the bot in 'live-now' channels and sends an initial message."""
        def is_me(m):
            return m.author == self.user

        for guild in self.guilds:
            live_channel = get(guild.channels, name='live-now')
            if live_channel and isinstance(live_channel, discord.TextChannel):
                try:
                    await live_channel.purge(check=is_me)
                    await live_channel.send(
                        "This is where active streams will show up! For your stream to show up, "
                        "it must mention FF6WC in some way.",
                        view=streamButton()
                    )
                except discord.errors.Forbidden:
                    logging.warning(f"No permissions to purge messages in '{live_channel.name}' on guild '{guild.name}'.")
                except Exception as e:
                    logging.error(f"Error purging channel in guild {guild.id}: {e}")

    @tasks.loop(minutes=1)
    async def get_streams_task(self):
        """The main task to fetch streams and update Discord."""
        try:
            # 1. Fetch all stream data from Twitch
            game_categories_config = await db_manager.get_all_config(self.db_conn, 'game_categories')
            blacklist = set((await db_manager.get_all_config(self.db_conn, 'blacklist')).values())

            all_streams = {}
            for cat_id, config_json in game_categories_config.items():
                try:
                    config = json.loads(config_json)
                    streams = await self.twitch_api.get_streams(cat_id)
                    for stream in streams:
                        if self._is_stream_valid(stream, config, blacklist):
                            all_streams[stream['id']] = stream
                except json.JSONDecodeError:
                    logging.error(f"Error decoding config for category ID: {cat_id}")
                except Exception as e:
                    logging.error(f"Error processing category {cat_id}: {e}")

            # 2. Enrich streams with profile pictures
            await self._enrich_streams_with_user_data(all_streams)

            # 3. Update Discord posts
            await self._update_discord_posts(all_streams)

        except Exception as e:
            logging.error(f"An unexpected error occurred in the main stream loop: {e}", exc_info=True)

    @get_streams_task.before_loop
    async def before_get_streams_task(self):
        await self.wait_until_ready()
        await self.purge_and_notify_channels()

    def _is_stream_valid(self, stream: dict, category_config: dict, blacklist: set) -> bool:
        """Checks if a stream meets the criteria to be posted."""
        title_lower = stream['title'].lower()
        user_name_lower = stream['user_name'].lower()

        if user_name_lower in blacklist:
            return False
        if user_name_lower in category_config.get('exclusions', []):
            return False
        if not any(kw in title_lower for kw in category_config.get('keywords', [])):
            return False

        return True

    async def _enrich_streams_with_user_data(self, streams: dict):
        """Fetches profile pictures for a list of streams in-place."""
        user_logins = [s['user_name'] for s in streams.values()]
        if not user_logins:
            return

        user_data = await self.twitch_api.get_users(user_logins)
        user_pics = {user['login']: user['profile_image_url'] for user in user_data}

        for stream_id, stream in streams.items():
            stream['pic'] = user_pics.get(stream['user_name'], None)

    async def _update_discord_posts(self, new_streams: dict):
        """Compares new streams with cached messages and updates Discord."""
        new_stream_ids = set(new_streams.keys())
        posted_stream_ids = {v['stream_id'] for v in self.current_stream_msgs.values()}

        # Post new streams
        streams_to_post = new_stream_ids - posted_stream_ids
        for stream_id in streams_to_post:
            stream = new_streams[stream_id]
            for guild in self.guilds:
                channel = get(guild.channels, name='live-now')
                if channel:
                    embed = self._create_stream_embed(stream)
                    try:
                        msg = await channel.send(embed=embed)
                        msg_key = f"{channel.id}_{stream_id}"
                        self.current_stream_msgs[msg_key] = {"stream_id": stream_id, "msg_id": msg.id, "channel_id": channel.id}
                    except Exception as e:
                        logging.error(f"Failed to send message for stream {stream_id} in guild {guild.id}: {e}")

        # Remove old streams
        streams_to_remove = posted_stream_ids - new_stream_ids
        for stream_id in streams_to_remove:
            # Find all messages associated with this stream_id and remove them
            keys_to_delete = [k for k, v in self.current_stream_msgs.items() if v['stream_id'] == stream_id]
            for key in keys_to_delete:
                msg_info = self.current_stream_msgs.pop(key)
                channel = self.get_channel(msg_info['channel_id'])
                if channel:
                    try:
                        message = await channel.fetch_message(msg_info['msg_id'])
                        await message.delete()
                    except discord.errors.NotFound:
                        pass # Message was already deleted
                    except Exception as e:
                        logging.error(f"Failed to delete message {msg_info['msg_id']} for stream {stream_id}: {e}")

    def _create_stream_embed(self, stream: dict) -> discord.Embed:
        """Creates a Discord embed for a given stream."""
        embed = discord.Embed(
            title=f'{stream["user_name"]} is streaming now!',
            url=f'https://twitch.tv/{stream["user_name"]}',
            description=stream['title'].strip(),
            color=discord.Color.random()
        )
        if stream.get('pic'):
            embed.set_thumbnail(url=stream['pic'])

        start_time_dt = datetime.datetime.strptime(stream["started_at"], "%Y-%m-%dT%H:%M:%SZ")
        start_timestamp = int(calendar.timegm(start_time_dt.utctimetuple()))
        embed.add_field(name="Started", value=f'<t:{start_timestamp}:R>')
        embed.add_field(name="Category", value=stream['game_name'])
        return embed

# --- Bot and Commands Setup ---
intents = discord.Intents.default()
client = StreamBot(intents=intents)

@client.tree.command(name="restart", description="Restart the bot (Admin only)")
@app_commands.check(check_admin)
async def restart(interaction: discord.Interaction):
    await interaction.response.send_message('Restarting bot...')
    restart_bot()

# --- Admin Command Group ---
admin_group = app_commands.Group(name="admin", description="Admin commands for bot configuration")

@admin_group.command(name="add_blacklist", description="Add a Twitch user to the blacklist")
async def add_blacklist(interaction: discord.Interaction, username: str):
    username_lower = username.lower()
    await db_manager.save_config(interaction.client.db_conn, 'blacklist', username_lower, username_lower)
    await interaction.response.send_message(f"Successfully added '{username}' to the blacklist.", ephemeral=True)

@admin_group.command(name="remove_blacklist", description="Remove a Twitch user from the blacklist")
async def remove_blacklist(interaction: discord.Interaction, username: str):
    if await db_manager.remove_config(interaction.client.db_conn, 'blacklist', username.lower()):
        await interaction.response.send_message(f"Successfully removed '{username}' from the blacklist.", ephemeral=True)
    else:
        await interaction.response.send_message(f"'{username}' was not found in the blacklist.", ephemeral=True)

@admin_group.command(name="add_category", description="Add a Twitch category to track")
async def add_category(interaction: discord.Interaction, category_id: str, name: str):
    try:
        int(category_id)
    except ValueError:
        await interaction.response.send_message("Invalid Category ID. Please enter a numeric ID.", ephemeral=True)
        return
    config_data = {"name": name, "keywords": [], "exclusions": []}
    await db_manager.save_config(interaction.client.db_conn, 'game_categories', category_id, json.dumps(config_data))
    await interaction.response.send_message(f"Successfully added category '{name}' ({category_id}).", ephemeral=True)

@admin_group.command(name="remove_category", description="Remove a Twitch category from tracking")
async def remove_category(interaction: discord.Interaction, category_id: str):
    if await db_manager.remove_config(interaction.client.db_conn, 'game_categories', category_id):
        await interaction.response.send_message(f"Successfully removed category ID '{category_id}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Category ID '{category_id}' was not found.", ephemeral=True)

@admin_group.command(name="add_keyword", description="Add a keyword to a category")
async def add_keyword(interaction: discord.Interaction, category_id: str, keyword: str):
    config = await get_category_config(interaction, category_id)
    if config is None: return

    keyword_lower = keyword.lower().strip()
    if keyword_lower not in config['keywords']:
        config['keywords'].append(keyword_lower)
        await db_manager.save_config(interaction.client.db_conn, 'game_categories', category_id, json.dumps(config))
        await interaction.response.send_message(f"Added keyword '{keyword}' to category '{config['name']}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Keyword '{keyword}' already exists in category '{config['name']}'.", ephemeral=True)

@admin_group.command(name="remove_keyword", description="Remove a keyword from a category")
async def remove_keyword(interaction: discord.Interaction, category_id: str, keyword: str):
    config = await get_category_config(interaction, category_id)
    if config is None: return

    keyword_lower = keyword.lower().strip()
    if keyword_lower in config['keywords']:
        config['keywords'].remove(keyword_lower)
        await db_manager.save_config(interaction.client.db_conn, 'game_categories', category_id, json.dumps(config))
        await interaction.response.send_message(f"Removed keyword '{keyword}' from category '{config['name']}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Keyword '{keyword}' not found in category '{config['name']}'.", ephemeral=True)

@admin_group.command(name="add_exclusion", description="Exclude a user from a category")
async def add_exclusion(interaction: discord.Interaction, category_id: str, username: str):
    config = await get_category_config(interaction, category_id)
    if config is None: return

    username_lower = username.lower().strip()
    if username_lower not in config['exclusions']:
        config['exclusions'].append(username_lower)
        await db_manager.save_config(interaction.client.db_conn, 'game_categories', category_id, json.dumps(config))
        await interaction.response.send_message(f"Added exclusion for '{username}' to category '{config['name']}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User '{username}' already excluded in category '{config['name']}'.", ephemeral=True)

@admin_group.command(name="remove_exclusion", description="Remove a user's exclusion from a category")
async def remove_exclusion(interaction: discord.Interaction, category_id: str, username: str):
    config = await get_category_config(interaction, category_id)
    if config is None: return

    username_lower = username.lower().strip()
    if username_lower in config['exclusions']:
        config['exclusions'].remove(username_lower)
        await db_manager.save_config(interaction.client.db_conn, 'game_categories', category_id, json.dumps(config))
        await interaction.response.send_message(f"Removed exclusion for '{username}' from category '{config['name']}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User '{username}' not found in exclusions for category '{config['name']}'.", ephemeral=True)

# Add the group to the command tree
client.tree.add_command(admin_group)

# Generic error handler for admin commands
async def on_admin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions for this command.", ephemeral=True)
    else:
        logging.error(f"An error occurred in an admin command: {error}", exc_info=True)
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)

for command in admin_group.commands:
    command.error(on_admin_error)

# --- Main Execution ---
async def main():
    db_manager.initialize_db()

    # We need a synchronous connection to get the token before starting the async loop
    sync_conn = get_sync_db_connection()
    discord_token = sync_conn.execute("SELECT value FROM config WHERE category = 'credentials' AND key = 'discord_token'").fetchone()
    sync_conn.close()

    if not discord_token:
        logging.error("Discord token not found in database. Please run the script once manually to configure it.")
        return

    try:
        await client.start(discord_token)
    except KeyboardInterrupt:
        pass
    finally:
        if not client.is_closed():
            await client.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError, discord.errors.ConnectionClosed):
        restart_bot()
