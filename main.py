import asyncio.exceptions
import copy
import datetime
import calendar
import http.client
import json
import os
import platform
import sys
from asyncio import sleep

import discord
from discord.ext import tasks, commands
from discord.utils import get
from discord import app_commands

import db_manager  # Assuming db_manager.py is in the same directory
from views import streamButton

stream_msg = {}
current_stream_msgs = {}


class aclient(commands.Bot):
    def __init__(self):
        # Retrieve the Discord token from the database
        discord_token = db_manager.get_config('credentials', 'discord_token')
        super().__init__(command_prefix='%^!', intents=discord.Intents.default(), token=discord_token)

    async def on_ready(self):
        await self.wait_until_ready()
        prfx = str(datetime.datetime.utcnow())
        print(prfx + " - Logged in as " + client.user.name)
        print(prfx + " - Bot ID: " + str(client.user.id))
        print(prfx + " - Discord Version: " + discord.__version__)
        print(prfx + " - Python Version: " + str(platform.python_version()))
        synclist = await client.tree.sync()
        print(prfx + " - Slash Commands Synced: " + str(len(synclist)))
        if not getstreams.is_running():
            await start_stream_list()


def check_admin(interaction: discord.Interaction):
    for x in interaction.user.roles:
        if x.name in ["Racebot Admin", "Moderation team", "Admins"]:
            return True
    return False


def restart_bot():
    os.execv(sys.executable, ['python3'] + sys.argv)


client = aclient()


@client.tree.command(name="restart", description="Restart the bot if it's having trouble (limited to certain roles)")
async def restart(interaction: discord.Interaction):
    if check_admin(interaction):
        await interaction.response.send_message('Restarting bot...')
        restart_bot()
    else:
        await interaction.response.send_message("Only Admins, Moderators and Racebot Admins can use that command!", ephemeral=True)

def refresh_token():
    conn = http.client.HTTPSConnection("id.twitch.tv")
    client_id = db_manager.get_config('credentials', 'twitch_client_id')
    client_secret = db_manager.get_config('credentials', 'twitch_client_secret')
    payload = f'client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    conn.request("POST", "/oauth2/token", payload, headers)
    res = conn.getresponse()
    data = res.read()
    x = data.decode("utf-8")
    j = json.loads(x)
    newtoken = j['access_token']
    db_manager.save_config('credentials', 'twitch_token', newtoken) # Save the new token to the database
    print(f"{datetime.datetime.utcnow()} - Twitch token refreshed and saved to database.")
    return newtoken


async def start_stream_list():
    await purge_channels()
    try:
        getstreams.start()
    except RuntimeError as e:
        print(f"Error in 'start_stream_list', attempting to restart task\nError: {e}")
        getstreams.stop()
        await sleep(10)
        try:
            getstreams.start()
        except RuntimeError as e2:
            print(f"First task restart didn't work, trying again in 2 minutes...\nError: {e2}")
            getstreams.stop()
            await sleep(120)
            getstreams.start()


async def purge_channels():
    def is_me(m):
        return m.author == client.user

    try:
        guilds = [guild async for guild in client.fetch_guilds()]
        for x in guilds:
            clean_channel = get(client.get_all_channels(), guild=x, name='live-now')
            await clean_channel.purge(check=is_me)
            await clean_channel.send("This is where all active streams will show up! For your stream to show up, "
                                        "it must mention FF6WC in some way.", view=streamButton())
    except AttributeError:
        print("dang")


@client.tree.command(name="add_blacklist", description="Add a Twitch user to the blacklist")
@app_commands.check(check_admin)
async def add_blacklist(interaction: discord.Interaction, username: str):
    """Adds a Twitch username to the blacklist.

    Args:
        username (str): The Twitch username to blacklist (case-insensitive).
    """
    username_lower = username.lower()
    # We'll use the username as the key for simplicity, though keys must be unique.
    # If we want to allow the same username to be added multiple times (which is unlikely),
    # we'd need a different key strategy (e.g., an auto-incrementing ID).
    db_manager.save_config('blacklist', username_lower, username_lower)
    await interaction.response.send_message(f"Successfully added '{username}' to the blacklist.", ephemeral=True)

@add_blacklist.error
async def add_blacklist_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while adding to the blacklist.", ephemeral=True)

@client.tree.command(name="remove_blacklist", description="Remove a Twitch user from the blacklist")
@app_commands.check(check_admin)
async def remove_blacklist(interaction: discord.Interaction, username: str):
    """Removes a Twitch username from the blacklist.

    Args:
        username (str): The Twitch username to remove (case-insensitive).
    """
    username_lower = username.lower()
    conn = db_manager.connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM config WHERE category = ? AND key = ?", ('blacklist', username_lower))
    conn.commit()
    conn.close()
    if cursor.rowcount > 0:
        await interaction.response.send_message(f"Successfully removed '{username}' from the blacklist.", ephemeral=True)
    else:
        await interaction.response.send_message(f"'{username}' was not found in the blacklist.", ephemeral=True)

@remove_blacklist.error
async def remove_blacklist_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while removing from the blacklist.", ephemeral=True)

@client.tree.command(name="add_category", description="Add a Twitch category ID to track with a custom name")
@app_commands.check(check_admin)
async def add_category(interaction: discord.Interaction, category_id: str, name: str):
    """Adds a Twitch category ID to the tracking list with a custom name.

    Args:
        category_id (str): The Twitch category ID to add (e.g., '18218').
        name (str): A user-friendly name for this category (e.g., 'Final Fantasy VI').
    """
    try:
        game_id = int(category_id)
    except ValueError:
        await interaction.response.send_message("Invalid Category ID. Please enter a numeric ID.", ephemeral=True)
        return

    config_data = {"name": name, "keywords": [], "exclusions": []}
    db_manager.save_config('game_categories', str(game_id), json.dumps(config_data))
    await interaction.response.send_message(f"Successfully added category ID '{category_id}' with name '{name}' to the tracking list.", ephemeral=True)

@add_category.error
async def add_category_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while adding the category.", ephemeral=True)

@client.tree.command(name="remove_category", description="Remove a Twitch category ID from tracking")
@app_commands.check(check_admin)
async def remove_category(interaction: discord.Interaction, category_id: str):
    """Removes a Twitch category ID from the tracking list.

    Args:
        category_id (str): The Twitch category ID to remove (e.g., '18218').
    """
    conn = db_manager.connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM config WHERE category = ? AND key = ?", ('game_categories', category_id))
    conn.commit()
    conn.close()
    if cursor.rowcount > 0:
        await interaction.response.send_message(f"Successfully removed category ID '{category_id}' from the tracking list.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Category ID '{category_id}' was not found in the tracking list.", ephemeral=True)

@remove_category.error
async def remove_category_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while removing the category.", ephemeral=True)

@client.tree.command(name="add_keyword", description="Add a keyword to a tracked category")
@app_commands.check(check_admin)
async def add_keyword(interaction: discord.Interaction, category_id: str, keyword: str):
    """Adds a keyword to a specific tracked category.

    Args:
        category_id (str): The ID of the category to add the keyword to.
        keyword (str): The keyword to add (case-insensitive).
    """
    category_config_json = db_manager.get_config('game_categories', category_id)
    if not category_config_json:
        await interaction.response.send_message(f"Category ID '{category_id}' not found.", ephemeral=True)
        return

    try:
        category_config = json.loads(category_config_json)
    except json.JSONDecodeError:
        await interaction.response.send_message(f"Error decoding configuration for category ID '{category_id}'.", ephemeral=True)
        return

    keyword_lower = keyword.lower().strip()
    if keyword_lower not in category_config['keywords']:
        category_config['keywords'].append(keyword_lower)
        db_manager.save_config('game_categories', category_id, json.dumps(category_config))
        await interaction.response.send_message(f"Successfully added keyword '{keyword}' to category ID '{category_id}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Keyword '{keyword}' is already in category ID '{category_id}'.", ephemeral=True)

@add_keyword.error
async def add_keyword_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while adding the keyword.", ephemeral=True)

@client.tree.command(name="remove_keyword", description="Remove a keyword from a tracked category")
@app_commands.check(check_admin)
async def remove_keyword(interaction: discord.Interaction, category_id: str, keyword: str):
    """Removes a keyword from a specific tracked category.

    Args:
        category_id (str): The ID of the category to remove the keyword from.
        keyword (str): The keyword to remove (case-insensitive).
    """
    category_config_json = db_manager.get_config('game_categories', category_id)
    if not category_config_json:
        await interaction.response.send_message(f"Category ID '{category_id}' not found.", ephemeral=True)
        return

    try:
        category_config = json.loads(category_config_json)
    except json.JSONDecodeError:
        await interaction.response.send_message(f"Error decoding configuration for category ID '{category_id}'.", ephemeral=True)
        return

    keyword_lower = keyword.lower().strip()
    if keyword_lower in category_config['keywords']:
        category_config['keywords'].remove(keyword_lower)
        db_manager.save_config('game_categories', category_id, json.dumps(category_config))
        await interaction.response.send_message(f"Successfully removed keyword '{keyword}' from category ID '{category_id}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Keyword '{keyword}' not found in category ID '{category_id}'.", ephemeral=True)

@remove_keyword.error
async def remove_keyword_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while removing the keyword.", ephemeral=True)

@client.tree.command(name="add_exclusion", description="Add a Twitch user to the exclusion list for a category")
@app_commands.check(check_admin)
async def add_exclusion(interaction: discord.Interaction, category_id: str, username: str):
    """Adds a Twitch username to the exclusion list for a specific category.

    Args:
        category_id (str): The ID of the category to add the exclusion to.
        username (str): The Twitch username to exclude (case-insensitive).
    """
    category_config_json = db_manager.get_config('game_categories', category_id)
    if not category_config_json:
        await interaction.response.send_message(f"Category ID '{category_id}' not found.", ephemeral=True)
        return

    try:
        category_config = json.loads(category_config_json)
    except json.JSONDecodeError:
        await interaction.response.send_message(f"Error decoding configuration for category ID '{category_id}'.", ephemeral=True)
        return

    username_lower = username.lower().strip()
    if username_lower not in category_config['exclusions']:
        category_config['exclusions'].append(username_lower)
        db_manager.save_config('game_categories', category_id, json.dumps(category_config))
        await interaction.response.send_message(f"Successfully added '{username}' to the exclusion list for category ID '{category_id}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"'{username}' is already in the exclusion list for category ID '{category_id}'.", ephemeral=True)

@add_exclusion.error
async def add_exclusion_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while adding the exclusion.", ephemeral=True)

@client.tree.command(name="remove_exclusion", description="Remove a Twitch user from the exclusion list for a category")
@app_commands.check(check_admin)
async def remove_exclusion(interaction: discord.Interaction, category_id: str, username: str):
    """Removes a Twitch username from the exclusion list for a specific category.

    Args:
        category_id (str): The ID of the category to remove the exclusion from.
        username (str): The Twitch username to remove (case-insensitive).
    """
    category_config_json = db_manager.get_config('game_categories', category_id)
    if not category_config_json:
        await interaction.response.send_message(f"Category ID '{category_id}' not found.", ephemeral=True)
        return

    try:
        category_config = json.loads(category_config_json)
    except json.JSONDecodeError:
        await interaction.response.send_message(f"Error decoding configuration for category ID '{category_id}'.", ephemeral=True)
        return

    username_lower = username.lower().strip()
    if username_lower in category_config['exclusions']:
        category_config['exclusions'].remove(username_lower)
        db_manager.save_config('game_categories', category_id, json.dumps(category_config))
        await interaction.response.send_message(f"Successfully removed '{username}' from the exclusion list for category ID '{category_id}'.", ephemeral=True)
    else:
        await interaction.response.send_message(f"'{username}' not found in the exclusion list for category ID '{category_id}'.", ephemeral=True)

@remove_exclusion.error
async def remove_exclusion_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("You do not have the necessary permissions to use this command.", ephemeral=True)
    else:
        print(f"An error occurred: {error}")
        await interaction.response.send_message("An unexpected error occurred while removing the exclusion.", ephemeral=True)

@tasks.loop(minutes=1)
async def getstreams():
    try:
        guilds = [guild async for guild in client.fetch_guilds()]
        game_categories_config = db_manager.get_all_config('game_categories')
        game_cats = {}
        for cat_id, config_json in game_categories_config.items():
            try:
                game_cats[int(cat_id)] = json.loads(config_json)
            except json.JSONDecodeError:
                print(f"Error decoding config for category ID: {cat_id}")
                continue
        blacklist_config = db_manager.get_all_config('blacklist')
        blacklist = set(blacklist_config.values())
        token = db_manager.get_config('credentials', 'twitch_token') # Get token from database on each loop
        if not token:
            token = refresh_token() # Refresh if it's not there for some reason

        global stream_msg
        n_streamlist = {}

        for gc_id, gc_config in game_cats.items():
            conn = http.client.HTTPSConnection("api.twitch.tv")
            payload = ''
            headers = {
                'Client-ID': db_manager.get_config('credentials', 'twitch_client_id'),
                'Authorization': f'Bearer {token}'
            }
            conn.request("GET", "/helix/streams?game_id=" + str(gc_id) + "&first=100", payload, headers)
            res = conn.getresponse()
            data = res.read()
            x = data.decode("utf-8")

            if res.status >= 400: # Check for any 4xx or 5xx status codes (errors)
                error_data = json.loads(x)
                print(f"{datetime.datetime.utcnow()} - Twitch API Error (Status {res.status}): {error_data}")
                if res.status == 401: # Specifically check for 401 Unauthorized (likely invalid token)
                    token = refresh_token() # Refresh the token
                    headers['Authorization'] = f'Bearer {token}' # Update headers
                    # Re-run the current API request
                    conn.request("GET", "/helix/streams?game_id=" + str(gc_id) + "&first=100", payload, headers)
                    res = conn.getresponse()
                    data = res.read()
                    x = data.decode("utf-8")
                else:
                    print(f"{datetime.datetime.utcnow()} - Non-token related Twitch API error, skipping this category.")
                    continue # Skip to the next game category

            j = json.loads(x)
            xx = j['data']
            if not j['pagination']:
                empty_page = True
                pag = ""
            else:
                pag = j['pagination']['cursor']
                empty_page = False

            while not empty_page:
                conn.request("GET", "/helix/streams?game_id=" + str(gc_id) + "&first=100&after=" + str(pag), payload,
                             headers)
                res = conn.getresponse()
                data = res.read()
                x = data.decode("utf-8")

                if res.status >= 400: # Check for errors again
                    error_data = json.loads(x)
                    print(f"{datetime.datetime.utcnow()} - Twitch API Error (Status {res.status}): {error_data}")
                    if res.status == 401:
                        token = refresh_token()
                        headers['Authorization'] = f'Bearer {token}'
                        conn.request("GET", "/helix/streams?game_id=" + str(gc_id) + "&first=100&after=" + str(pag), payload,
                                     headers)
                        res = conn.getresponse()
                        data = res.read()
                        x = data.decode("utf-8")
                    else:
                        print(f"{datetime.datetime.utcnow()} - Non-token related Twitch API error during pagination, skipping the rest of this category's pages.")
                        empty_page = True # Stop fetching further pages for this category
                        continue

                j = json.loads(x)
                try:
                    if not j['pagination']:
                        empty_page = True
                        pass
                    else:
                        pag = j['pagination']['cursor']
                        xx += j['data']
                except KeyError:
                    print(j)
                k = len(xx)

                while k != 0:
                    if any(ac in xx[k - 1]['title'].lower() for ac in gc_config['exclusions']):
                        pass
                    # Skip any streamer in the blacklist (case-insensitive)
                    elif xx[k - 1]['user_name'].lower() in blacklist:
                        pass
                    elif any(ac in xx[k - 1]['title'].lower() for ac in gc_config['keywords']):
                        aa = xx[k - 1]
                        conn.request("GET", "/helix/users?login=" + str(aa["user_name"]), payload, headers)
                        res = conn.getresponse()
                        # We should also check the status code for this request, but for now let's keep it simpler.
                        data = res.read()
                        y = data.decode("utf-8")
                        g = json.loads(y)
                        gg = g['data']
                        index = aa['id']
                        n_streamlist[index] = {"user_name": aa["user_name"], "title": aa["title"],
                                                "started_at": aa["started_at"], "category": aa["game_name"], "pic": gg[0]["profile_image_url"], "start_time": xx[0]["started_at"]}
                    k -= 1

        for x in n_streamlist:
            if any(str(x) in d.values() for d in current_stream_msgs.values()):
                pass
            else:
                for g in guilds:
                    channel = get(client.get_all_channels(), guild=g, name='live-now')
                    embed = discord.Embed()
                    embed.title = f'{n_streamlist[x]["user_name"]} is streaming now!'
                    embed.url = f'https://twitch.tv/{n_streamlist[x]["user_name"]}'
                    embed.description = f'{n_streamlist[x]["title"].strip()}'
                    embed.set_thumbnail(url=n_streamlist[x]["pic"])
                    embed.add_field(name="Started:", value=f'<t:{calendar.timegm(datetime.datetime.strptime(n_streamlist[x]["started_at"],"%Y-%m-%dT%H:%M:%SZ").utctimetuple())}:R>')
                    embed.colour = discord.Colour.random()
                    msg = await channel.send(embed=embed)
                    msg_key = '_'.join([str(channel.id), str(x)])
                    current_stream_msgs[msg_key] = {"stream_id": x, "msg_id": msg.id, "channel": channel.id,
                                                    "title": n_streamlist[x]['title'].strip(),
                                                    "category": n_streamlist[x]['category']}
        for y, v in copy.deepcopy(current_stream_msgs).items():
            if v['stream_id'] not in n_streamlist.keys():
                channel = client.get_channel(v['channel'])
                message = await channel.fetch_message(v['msg_id'])
                try:
                    await message.delete()
                except:
                    del current_stream_msgs[v]
            elif v['stream_id'] in n_streamlist.keys() and (v['title'] != n_streamlist[v['stream_id']]['title']):
                channel = client.get_channel(v['channel'])
                message = await channel.fetch_message(v['msg_id'])
                try:
                    await message.delete()
                    del current_stream_msgs[y]
                except:
                    del current_stream_msgs[y]
        for k, u in copy.deepcopy(current_stream_msgs).items():
            if u['stream_id'] not in n_streamlist.keys():
                del current_stream_msgs[k]

    except discord.errors.HTTPException as e:
        print(f"Error: {e}")
        await sleep(5)
        pass
    except RuntimeError as e:
        print(f"Error: {e}")
        getstreams.stop()
        await sleep(10)
        try:
            getstreams.start()
        except RuntimeError as e2:
            print(f"First task restart didn't work, trying again in 2 minutes...\nError: {e2}")
            getstreams.stop()
            await sleep(120)
            getstreams.start()
        pass


try:
    client.run(db_manager.get_config('credentials', 'discord_token'))
except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError, discord.errors.ConnectionClosed):
    restart_bot()