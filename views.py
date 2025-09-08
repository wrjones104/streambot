import json
import logging
import discord
from discord.ui import View
import db_manager

class streamButton(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(label="See Keywords", style=discord.ButtonStyle.green, custom_id="keywords")
    async def get_keywords(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            # The bot instance is available via interaction.client
            client = interaction.client
            if not client.db_conn:
                await interaction.followup.send("Database connection is not available.", ephemeral=True)
                return

            game_categories_config = await db_manager.get_all_config(client.db_conn, 'game_categories')

            if not game_categories_config:
                await interaction.followup.send("No tracked categories found.", ephemeral=True)
                return

            response_lines = []
            for cat_id, config_json in game_categories_config.items():
                try:
                    category_config = json.loads(config_json)
                    # The hardcoded exclusion for cat_id "5815" has been removed.
                    # If certain categories need to be hidden from this list,
                    # a more robust solution would be to add a 'hidden' flag
                    # to the category's configuration in the database.

                    name = category_config.get("name", "Unknown")
                    keywords = category_config.get("keywords", [])

                    if keywords:
                        keyword_str = ", ".join(keywords)
                        response_lines.append(f'**{name} ({cat_id})**: ```{keyword_str}```')
                    else:
                        response_lines.append(f'**{name} ({cat_id})**: ```No keywords configured.```')

                except json.JSONDecodeError:
                    logging.warning(f"Error decoding config for category ID: {cat_id} in get_keywords view.")
                    continue

            response_text = "\n".join(response_lines)
            if not response_text:
                response_text = "No categories with keywords are configured."

            await interaction.followup.send(response_text, ephemeral=True)

        except Exception as e:
            logging.error(f"Error in get_keywords button callback: {e}", exc_info=True)
            # Check if the interaction is still valid before sending a followup
            if not interaction.is_expired():
                await interaction.followup.send("An error occurred while fetching keywords. Please try again later.", ephemeral=True)
