import sqlite3
import http.client
import db.tokens as tokens
import json

async def db_con():
    con = sqlite3.connect("db/cbdb.sqlite")
    cur = con.cursor()
    return con, cur

def init_db():
    con = sqlite3.connect("db/cbdb.sqlite")
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS streamers (twitch_user TEXT PRIMARY KEY)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, user_name TEXT)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS tags (tag_name TEXT PRIMARY KEY)"
    )
    cur.execute(
        "CREATE TABLE IF NOT EXISTS credentials (twitch_token TEXT PRIMARY KEY)"
    )
    con.commit()
    con.close()


async def get_user(uid):
    con, cur = await db_con()
    cur.execute("SELECT * FROM users WHERE user_id = (?)", (uid,))
    user = cur.fetchone()
    con.close()
    return user

async def get_users():
    con, cur = await db_con()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    con.close()
    return users

async def add_user(uid, uname):
    con, cur = await db_con()
    cur.execute(
        "INSERT OR REPLACE INTO users (user_id, user_name) VALUES (?, ?)",
        (uid, uname),
    )
    con.commit()
    con.close()

async def del_user(uname):
    con, cur = await db_con()
    cur.execute("SELECT * FROM users WHERE user_name = (?) COLLATE NOCASE", (uname,))
    user = cur.fetchone()
    if not user:
        return None
    cur.execute("DELETE FROM users WHERE user_name = (?) COLLATE NOCASE", (uname,))
    con.commit()
    con.close()
    return True

async def add_streamer(tu):
    con, cur = await db_con()
    cur.execute(
        "INSERT OR REPLACE INTO streamers (twitch_user) VALUES (?)",
        (tu,),
    )
    con.commit()
    con.close()

async def del_streamer(tu):
    con, cur = await db_con()
    cur.execute("DELETE FROM streamers WHERE twitch_user = (?)", (tu,))
    con.commit()
    con.close()

async def add_tag(t):
    con, cur = await db_con()
    cur.execute(
        "INSERT OR REPLACE INTO tags (tag_name) VALUES (?)",
        (t,),
    )
    con.commit()
    con.close()

async def del_tag(t):
    con, cur = await db_con()
    cur.execute(
        "DELETE FROM tags WHERE tag_name = (?)",
        (t,),
    )
    con.commit()
    con.close()

async def get_streamers():
    con, cur = await db_con()
    cur.execute("SELECT twitch_user FROM streamers")
    streamers = cur.fetchall()
    con.close()
    return streamers

async def get_tags():
    con, cur = await db_con()
    cur.execute("SELECT tag_name FROM tags")
    tags = cur.fetchall()
    con.close()
    return tags

def get_token():
    con = sqlite3.connect("db/cbdb.sqlite")
    cur = con.cursor()
    cur.execute("SELECT twitch_token FROM credentials")
    token = cur.fetchone()
    con.close()
    return token

def first_token():
    conn = http.client.HTTPSConnection("id.twitch.tv")
    payload = f'client_id={tokens.client_id}&client_secret={tokens.secret}&grant_type=client_credentials'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    conn.request("POST", "/oauth2/token", payload, headers)
    res = conn.getresponse()
    data = res.read()
    x = data.decode("utf-8")
    j = json.loads(x)
    newtoken = j['access_token']
    print(f'newtoken={newtoken}')
    con = sqlite3.connect("db/cbdb.sqlite")
    cur = con.cursor()
    cur.execute("INSERT OR REPLACE into credentials (twitch_token) VALUES (?)", (newtoken,))
    con.commit()
    con.close()
    return newtoken

def refresh_token():
    conn = http.client.HTTPSConnection("id.twitch.tv")
    payload = {
        'client_id': tokens.client_id,
        'client_secret': tokens.secret,
        'grant_type': 'client_credentials'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    conn.request("POST", "/oauth2/token", payload, headers)
    res = conn.getresponse()
    data = res.read()
    x = data.decode("utf-8")
    j = json.loads(x)
    newtoken = j['access_token']
    print(f'refresh token={newtoken}')
    con = sqlite3.connect("db/cbdb.sqlite")
    cur = con.cursor()
    cur.execute("SELECT twitch_token FROM credentials")
    curtoken = cur.fetchone()
    cur.execute("UPDATE credentials SET twitch_token = (?) WHERE twitch_token = (?)", (newtoken, curtoken))
    con.commit()
    con.close()