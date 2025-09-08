import aiohttp
import db_manager
import datetime

class TwitchAPI:
    def __init__(self, client_id: str, client_secret: str, db_conn):
        self.client_id = client_id
        self.client_secret = client_secret
        self.db_conn = db_conn
        self._session = aiohttp.ClientSession(base_url="https://api.twitch.tv")
        self._token = None

    async def close(self):
        await self._session.close()

    async def _get_token(self):
        if self._token:
            return self._token
        token = await db_manager.get_config(self.db_conn, 'credentials', 'twitch_token')
        if not token:
            token = await self.refresh_token()
        self._token = token
        return token

    async def refresh_token(self):
        url = "https://id.twitch.tv/oauth2/token"
        params = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }
        async with self._session.post(url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            new_token = data['access_token']
            await db_manager.save_config(self.db_conn, 'credentials', 'twitch_token', new_token)
            self._token = new_token
            print(f"{datetime.datetime.utcnow()} - Twitch token refreshed and saved to database.")
            return new_token

    async def _request(self, method, path, params=None, headers=None):
        if headers is None:
            headers = {}
        token = await self._get_token()
        headers.update({
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {token}'
        })

        async with self._session.request(method, path, params=params, headers=headers) as resp:
            if resp.status == 401:
                # Token expired, refresh and retry once.
                await self.refresh_token()
                token = await self._get_token() # get the new token
                headers['Authorization'] = f'Bearer {token}'
                async with self._session.request(method, path, params=params, headers=headers) as retry_resp:
                    retry_resp.raise_for_status()
                    return await retry_resp.json()

            resp.raise_for_status()
            return await resp.json()

    async def get_streams(self, category_id: str, limit: int = 100):
        all_streams = []
        params = {'game_id': category_id, 'first': limit}
        while True:
            data = await self._request("GET", "/helix/streams", params=params)
            streams = data.get('data', [])
            all_streams.extend(streams)

            cursor = data.get('pagination', {}).get('cursor')
            if not cursor:
                break
            params['after'] = cursor

        return all_streams

    async def get_users(self, user_logins: list[str]):
        if not user_logins:
            return []

        all_users = []
        # Twitch API allows fetching up to 100 users at a time
        for i in range(0, len(user_logins), 100):
            chunk = user_logins[i:i+100]
            params = [('login', login) for login in chunk]
            data = await self._request("GET", "/helix/users", params=params)
            all_users.extend(data.get('data', []))

        return all_users
