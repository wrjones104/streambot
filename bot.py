import asyncio.exceptions
import copy
import datetime
import http.client
import traceback
import json
import os
import platform
import sys
from asyncio import sleep

import discord
from discord.ext import tasks, commands
from discord.utils import get
from discord.ui import Modal, TextInput
from discord import Interaction, TextStyle

import db.tokens as tokens
import functions
from views import streamButton

stream_msg = {}
current_stream_msgs = {}


class aclient(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='%^!', intents=discord.Intents.default())

    async def on_ready(self):
        await self.wait_until_ready()
        print(f"{datetime.datetime.utcnow()} - Logged in as " + client.user.name)
        print(f"{datetime.datetime.utcnow()} - Bot ID: " + str(client.user.id))
        print(f"{datetime.datetime.utcnow()} - Discord Version: " + discord.__version__)
        print(
            f"{datetime.datetime.utcnow()} - Python Version: "
            + str(platform.python_version())
        )
        synclist = await self.tree.sync()
        print(
            f"{datetime.datetime.utcnow()} - Slash Commands Synced: "
            + str(len(synclist))
        )
        functions.init_db()
        print(f"{datetime.datetime.utcnow()} - Databases Initialized!")
        if not getstreams.is_running():
            await start_stream_list()

class NewUserModal(Modal):
    username = TextInput(
        label="Enter the user's Discord name",
        style=TextStyle.short,
    )
    
    userid = TextInput(
        label="Enter the user's Discord ID",
        style=TextStyle.short,
    )

    def __init__(self, title: str) -> None:
        super().__init__(title=title, timeout=None)

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()

class StreamerModal(Modal):
    streamer = TextInput(
        label="Enter the streamer's Twitch name",
        style=TextStyle.short,
    )

    def __init__(self, title: str) -> None:
        super().__init__(title=title, timeout=None)

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()


class TagModal(Modal):
    tag = TextInput(
        label="Enter the tag name",
        style=TextStyle.short,
    )

    def __init__(self, title: str) -> None:
        super().__init__(title=title, timeout=None)

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()

class DelUserModal(Modal):
    username = TextInput(
        label="Enter the user's name",
        style=TextStyle.short,
    )

    def __init__(self, title: str) -> None:
        super().__init__(title=title, timeout=None)

    async def on_submit(self, interaction: Interaction, /) -> None:
        await interaction.response.defer()


def restart_bot():
    os.execv(sys.executable, ['python3'] + sys.argv)


client = aclient()


@client.tree.command(name="restart", description="Restart the bot if it's having trouble (admins only)")
async def restart(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        await interaction.response.send_message('Restarting bot...')
        restart_bot()
    else:
        await interaction.response.send_message("Only bot admins may use that command.", ephemeral=True)

@client.tree.command(name="register", description="Register a new streamer.")
async def register(interaction: discord.Interaction):
    modal = StreamerModal("Add a new streamer")
    await interaction.response.send_modal(modal)
    await modal.wait()
    await functions.add_streamer(str(modal.streamer))
    return await interaction.followup.send(f"{str(modal.streamer)} added!", ephemeral=True)

@client.tree.command(name='unregister', description="Unregister a streamer (admins only)")
async def unregister(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        modal = StreamerModal("Delete a streamer")
        await interaction.response.send_modal(modal)
        await modal.wait()
        await functions.del_streamer(str(modal.streamer))
        return await interaction.followup.send(f"{str(modal.streamer)} deleted!", ephemeral=True)
    else:
        await interaction.response.send_message("Only bot admins may use this command.", ephemeral=True)

@client.tree.command(name="newtag", description="Register a new tag (admins only).")
async def newtag(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        modal = TagModal("Add a new tag")
        await interaction.response.send_modal(modal)
        await modal.wait()
        await functions.add_tag(str(modal.tag))
        return await interaction.followup.send(f"{str(modal.tag)} added!", ephemeral=True)
    else:
        await interaction.response.send_message("Only bot admins may use this command.", ephemeral=True)

@client.tree.command(name="removetag", description="Register a new tag (admins only).")
async def removetag(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        modal = TagModal("Remove a tag")
        await interaction.response.send_modal(modal)
        await modal.wait()
        await functions.del_tag(str(modal.tag))
        return await interaction.followup.send(f"{str(modal.tag)} removed!", ephemeral=True)
    else:
        await interaction.response.send_message("Only bot admins may use this command.", ephemeral=True)

@client.tree.command(name="adduser", description="Register a bot user (admins only).")
async def adduser(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        modal = NewUserModal("Register a new user")
        await interaction.response.send_modal(modal)
        await modal.wait()
        await functions.add_user(str(modal.userid), str(modal.username))
        return await interaction.followup.send(f"{str(modal.username)} added!", ephemeral=True)
    else:
        await interaction.response.send_message("Only bot admins may use this command.", ephemeral=True)

@client.tree.command(name="deluser", description="Unregister a bot user (admins only).")
async def deluser(interaction: discord.Interaction):
    user = await functions.get_user(interaction.user.id)
    if user:
        modal = DelUserModal("Unregister a new user")
        await interaction.response.send_modal(modal)
        await modal.wait()
        check = await functions.del_user(str(modal.username))
        if check:
            return await interaction.followup.send(f"{str(modal.username)} removed!", ephemeral=True)
        else:
            return await interaction.followup.send("I could not find that user in the database.", ephemeral=True)
    else:
        await interaction.response.send_message("Only bot admins may use this command.", ephemeral=True)

@client.tree.command(name="userlist", description="Show a list of all bot users")
async def userlist(interaction: discord.Interaction):
    users = await functions.get_users()
    userlist = []
    for x in users:
        userlist.append(x[1])
    return await interaction.response.send_message(f"Here are all registered users:\n```{', '.join(userlist)}```", ephemeral=True)

@client.tree.command(name="streamerlist", description="Show a list of all registered streamers")
async def streamerlist(interaction: discord.Interaction):
    users = await functions.get_streamers()
    userlist = ""
    for x in users:
        userlist += f'{x[0]}\n'
    return await interaction.response.send_message(f"Here are all registered streamers:\n```{userlist}```", ephemeral=True)


async def start_stream_list():
    # When StreamBot logs in, it's going to prepare all "live-now" channels by clearing
    # all previous messages from itself.
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
                                     "you must `/register` your Twitch user name and include a supported tag in your stream.", view=streamButton())
    except AttributeError:
        print("dang")


@tasks.loop(minutes=1)
async def getstreams():
    try:
        # We're going to load the streamers and tags here. We do this on every run so that any changes to the bot's database are reflected immediately.
        guilds = [guild async for guild in client.fetch_guilds()]
        streamers = await functions.get_streamers()
        intags = await functions.get_tags()
        tags = []
        for t in intags:
            tags.append(t[0])
        global stream_msg
        n_streamlist = {}
        try:
            token = functions.get_token()[0]
        except TypeError:
            token = functions.first_token()[0]


        # This next part searches the Twitch API for the streamers and tags
        try:
            for s in streamers:
                conn = http.client.HTTPSConnection("api.twitch.tv")
                payload = ''
                headers = {
                    'Client-ID': tokens.client_id,
                    'Authorization': f'Bearer {token}'
                }
                conn.request("GET", "/helix/streams?user_login=" + str(s[0]).replace(" ",""), payload, headers)
                res = conn.getresponse()
                data = res.read()
                x = data.decode("utf-8")
                conn.request("GET", "/helix/users?login=" + str(s[0]).replace(" ",""), payload, headers)
                res = conn.getresponse()
                data = res.read()
                y = data.decode("utf-8")
                # Twitch's API requires a refreshed token every 90 days. If it's time to refresh, the bot will do that here.
                if "Invalid OAuth token" in x:
                    token = functions.refresh_token()
                    return
                elif "Malformed query params" in x:
                    print(f'{str(s[0])} is a bad entry - review and fix')
                    pass
                else:
                    j = json.loads(x)
                    k = json.loads(y)
                    xx = j['data']
                    yy = k['data']
                    if xx:
                        if any(ac in map(str.lower,xx[0]['tags']) for ac in map(str.lower,tags)):
                            n_streamlist[s[0]] = {"user_name": xx[0]["user_name"], "title": xx[0]["title"],
                                    "started_at": xx[0]["started_at"], "category": xx[0]["game_name"], "pic": yy[0]["profile_image_url"]}
                    

        except IndexError:
            return print(f'Error: {traceback.format_exc()}')

        # Here we're going to create discord messages when a new stream shows up in the list. We're also going to delete
        # messages after a stream has gone offline.
        for x in n_streamlist:
            if any(str(x) in d.values() for d in current_stream_msgs.values()):
                pass
            else:
                for g in guilds:
                    channel = get(client.get_all_channels(), guild=g, name='live-now')
                    embed = discord.Embed()
                    embed.title = f'{n_streamlist[x]["user_name"]} is streaming {n_streamlist[x]["category"]}!'
                    embed.url = f'https://twitch.tv/{n_streamlist[x]["user_name"]}'
                    embed.description = f'{n_streamlist[x]["title"].strip()}'
                    embed.set_thumbnail(url=n_streamlist[x]["pic"])
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
                except Exception:
                    del current_stream_msgs[v]
            elif v['stream_id'] in n_streamlist.keys() and (v['title'] != n_streamlist[v['stream_id']]['title']):
                channel = client.get_channel(v['channel'])
                message = await channel.fetch_message(v['msg_id'])
                try:
                    await message.delete()
                    del current_stream_msgs[y]
                except Exception:
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
    client.run(tokens.DISCORD_TOKEN)
except (asyncio.exceptions.TimeoutError, asyncio.exceptions.CancelledError, discord.errors.ConnectionClosed):
    restart_bot()
