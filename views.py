import discord
import functions
from discord.ui import View


class streamButton(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None

    @discord.ui.button(label="See Tags", style=discord.ButtonStyle.green,
                       custom_id="tags")
    async def get_keywords(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
            x = await functions.get_tags()
            tags = []
            for y in x:
                tags.append(y[0])
            keywords = f'**Tags**: ```{", ".join(tags)}```\n'
            await interaction.followup.send(f'{keywords}',
                                            ephemeral=True)
        except (discord.errors.HTTPException, discord.errors.NotFound):
            await interaction.response.defer()
            await interaction.followup.send("I'm a little overloaded - give me a sec and try again",
                                            ephemeral=True)
        except IndexError:
            pass
