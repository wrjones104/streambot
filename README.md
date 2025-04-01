# Discord Twitch Stream Bot

This Python-based Discord bot monitors Twitch streams and sends notifications to a designated Discord channel. It provides administrators with tools to manage tracked categories, keywords, and excluded streamers.

## Features

* **Twitch Stream Monitoring:** The bot periodically checks for live streams on Twitch based on configured game categories.
* **Discord Notifications:** When a relevant stream is found, the bot sends an embed message to the Discord channel, including the streamer's name, stream title, and a link to the stream.
* **Category Management:** Administrators can add and remove Twitch category IDs that the bot should track.
* **Keyword Filtering:** For each tracked category, administrators can define keywords. The bot only sends notifications for streams whose titles contain these keywords.
* **Exclusion List:** Administrators can add Twitch usernames to an exclusion list to prevent notifications for specific streamers within a category.
* **Blacklist:** Administrators can maintain a blacklist of Twitch users to be ignored by the bot.
* **Database Storage:** The bot uses an SQLite database (`bot_config.db`) to store configuration data, including tracked categories, keywords, exclusions, and Twitch API credentials.
* **Twitch Token Management:** The bot automatically refreshes its Twitch API access token as needed.
* **Slash Commands:** The bot utilizes Discord slash commands for easy administration.

## Setup

### Prerequisites

* Python 3.x
* `pip` package manager
* A Discord bot token
* Twitch API Client ID and Client Secret

### Installation

1.  Clone the repository:
    ```bash
    git clone <repository_url>
    ```
2.  Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Database Setup:**
    * The bot uses an SQLite database named `bot_config.db`. It will be created automatically if it doesn't exist.
4.  **Configuration:**
    * You will need to set up your Discord bot token, Twitch Client ID, and Twitch Client Secret. These values are stored in the database. You can use the bot's commands to set these, or you can manually add them to the database.
5.  **Run the Bot:**
    ```bash
    python main.py
    ```

## Bot Commands

### Admin Commands

* `/restart`: Restarts the bot.
* `/add_blacklist <username>`: Adds a Twitch user to the blacklist.
* `/remove_blacklist <username>`: Removes a Twitch user from the blacklist.
* `/add_category <category_id> <name>`: Adds a Twitch category to track.
* `/remove_category <category_id>`: Removes a Twitch category from tracking.
* `/add_keyword <category_id> <keyword>`: Adds a keyword to a tracked category.
* `/remove_keyword <category_id> <keyword>`: Removes a keyword from a tracked category.
* `/add_exclusion <category_id> <username>`: Adds a Twitch user to the exclusion list for a category.
* `/remove_exclusion <category_id> <username>`: Removes a Twitch user from the exclusion list for a category.

### User Commands

* The bot also has a "See Keywords" button in its messages.
