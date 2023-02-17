import json

import discord
from discord.ui import View


class streamButton(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(label="See Keywords", style=discord.ButtonStyle.green,
                       custom_id="keywords")
    async def get_keywords(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            with open("db/game_cats.json") as x:
                keywords = ""
                gcats = json.load(x)
                for y, z in gcats.items():
                    if y == "5815":
                        pass
                    else:
                        keywords += f'**{z["Name"]}**: ```{", ".join(z["keywords"])}```\n'
            await interaction.followup.send(f'{keywords}',
                                            ephemeral=True)
        except (discord.errors.HTTPException, discord.errors.NotFound):
            await interaction.response.defer()
            await interaction.followup.send(f"I'm a little overloaded - give me a sec and try again",
                                            ephemeral=True)
