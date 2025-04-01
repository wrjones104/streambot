import json

import discord
from discord.ui import View
import db_manager


class streamButton(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(label="See Keywords", style=discord.ButtonStyle.green,
                       custom_id="keywords")
    async def get_keywords(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            game_categories_config = db_manager.get_all_config('game_categories')
            keywords = ""
            for cat_id, config_json in game_categories_config.items():
                try:
                    category_config = json.loads(config_json)
                    if cat_id == "5815":  # Twitch's extra FFXVI category
                        pass
                    else:
                        keywords += f'**{category_config["name"]} ({cat_id})**: ```{", ".join(category_config["keywords"])}```\n'  # Added category ID

                except json.JSONDecodeError:
                    print(f"Error decoding config for category ID: {cat_id}")
                    continue  # Skip to the next category

            await interaction.followup.send(f'{keywords}', ephemeral=True)

        except (discord.errors.HTTPException, discord.errors.NotFound) as e:
            print(f"Error in get_keywords: {e}")
            await interaction.response.defer()
            await interaction.followup.send(f"I'm a little overloaded - give me a sec and try again", ephemeral=True)
