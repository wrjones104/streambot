import copy
import http.client
import json
from asyncio import sleep

import discord
from discord.ext import tasks
from discord.utils import get

import db.tokens as tokens

stream_msg = {}
current_stream_msgs = {}


class aclient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())

    async def on_ready(self):
        await self.wait_until_ready()
        print(f"We have logged in as {self.user}.")
        await start_stream_list()


client = aclient()


async def start_stream_list():
    # When StreamBot logs in, it's going to prepare all "live-now" channels by clearing
    # all previous messages from itself and posting an initial message which will act as the "edit" anchor
    await purge_channels()
    try:
        getstreams.start()
    except RuntimeError:
        getstreams.stop()
        await sleep(10)
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
                                     "it must mention FF6WC in some way.")
    except AttributeError:
        print("dang")


@tasks.loop(minutes=1)
async def getstreams():
    try:
        # We're going to load the keywords file into a dictionary. We're doing this here so that it reads the file on
        # every loop, which allows us to edit the files while the bot is running. This is helpful for if we want to add
        # channels, categories or keywords without having to restart the bot.
        guilds = [guild async for guild in client.fetch_guilds()]
        with open('db/game_cats.json') as gc:
            game_cats = json.load(gc)
        global stream_msg
        n_streamlist = {}

        # This next part searches the Twitch API for all categories and keywords that are specified in the
        # "game_cats.json" file
        for gc in game_cats:
            conn = http.client.HTTPSConnection("api.twitch.tv")
            payload = ''
            headers = {
                'Client-ID': tokens.client_id,
                'Authorization': tokens.twitch_token
            }
            conn.request("GET", "/helix/streams?game_id=" + str(gc) + "&first=100", payload, headers)
            res = conn.getresponse()
            data = res.read()
            x = data.decode("utf-8")

            # Twitch's API requires a refreshed token every 90 days. Chances are, I'm going to forget about this so this
            # message is a reminder if that happens! :)
            if "Invalid OAuth token" in x:
                for g in guilds:
                    channel = get(client.get_all_channels(), guild=g, name='live-now')
                    await purge_channels()
                    await channel.send("BZZZZZZT!!!\n---------------------\nTwitch OAuth token expired. Tell Jones!")
                    return getstreams.stop()
                break
            j = json.loads(x)
            xx = j['data']
            if not j['pagination']:
                empty_page = True
                pag = ""
            else:
                pag = j['pagination']['cursor']
                empty_page = False

            # Twitch's API will only return 100 streams max per call along with a "cursor" which you can use in a
            # follow-up call to get the next 100 streams. This part just loops through all "pages" until it reaches an
            # empty one (which means it's at the end)
            while not empty_page:
                conn.request("GET", "/helix/streams?game_id=" + str(gc) + "&first=100&after=" + str(pag), payload,
                             headers)
                res = conn.getresponse()
                data = res.read()
                x = data.decode("utf-8")
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

            # This part takes k (the amount of streams returned total) and uses it to iterate through all the returned
            # streams to find any with keywords from the "game_cats.json" file in the title of the stream
            while k != 0:
                if any(ac in xx[k - 1]['title'].lower() for ac in game_cats[gc]['exclusions']):
                    pass
                elif any(ac in xx[k - 1]['title'].lower() for ac in game_cats[gc]['keywords']):
                    aa = xx[k - 1]
                    index = aa['id']
                    n_streamlist[index] = {"user_name": aa["user_name"], "title": aa["title"],
                                           "started_at": aa["started_at"], "category": aa["game_name"]}
                k -= 1

        # Here we're going to create discord messages when a new stream shows up in the list. We're also going to delete
        # messages after a stream has gone offline. Finally, if we go from 0 to >1 active stream (or vice-versa), we're
        # going to edit the initial message
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
        getstreams.start()
        pass


client.run(tokens.DISCORD_TOKEN)
