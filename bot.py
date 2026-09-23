"""Discord bot that lets members share how available they are and ranks them."""

import os
from typing import Optional

import discord
from discord import app_commands
from dotenv import load_dotenv

from storage import Status, Storage

LEVELS = {
    1: ("🟢", "Totally free"),
    2: ("🟡", "Mostly free"),
    3: ("🟠", "Somewhat busy"),
    4: ("🔴", "Busy"),
    5: ("⛔", "Swamped"),
}
BUSYNESS_CHOICES = [
    app_commands.Choice(name=f"{n} – {label}", value=n) for n, (_, label) in LEVELS.items()
]
MAX_LIST = 25


def describe(busyness: int) -> str:
    emoji, label = LEVELS[busyness]
    return f"{emoji} {busyness}/5 · {label}"


def status_line(status: Status) -> str:
    line = f"<@{status.user_id}> — {describe(status.busyness)}"
    if status.note:
        line += f" — *{discord.utils.escape_markdown(status.note)}*"
    return line + f" · <t:{status.updated_at}:R>"


class AvailabilityBot(discord.Client):
    def __init__(self, storage: Storage, guild_id: Optional[int] = None):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.storage = storage
        self.sync_guild_id = guild_id

    async def setup_hook(self) -> None:
        register_commands(self.tree, self.storage)
        if self.sync_guild_id:
            guild = discord.Object(id=self.sync_guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id {self.user.id})")


def register_commands(tree: app_commands.CommandTree, storage: Storage) -> None:
    @tree.command(name="available", description="Mark yourself as available and say how busy you are")
    @app_commands.guild_only()
    @app_commands.describe(busyness="How busy you are (1 = totally free, 5 = swamped)",
                           note="Optional note, e.g. 'free after 6pm'")
    @app_commands.choices(busyness=BUSYNESS_CHOICES)
    async def available(interaction: discord.Interaction, busyness: app_commands.Choice[int],
                        note: Optional[app_commands.Range[str, 1, 100]] = None):
        status = storage.set_status(interaction.guild_id, interaction.user.id, busyness.value, note)
        await interaction.response.send_message(
            f"You're now listed as available: {describe(status.busyness)}", ephemeral=True
        )

    @tree.command(name="busy", description="Update how busy you are without changing your note")
    @app_commands.guild_only()
    @app_commands.describe(busyness="How busy you are (1 = totally free, 5 = swamped)")
    @app_commands.choices(busyness=BUSYNESS_CHOICES)
    async def busy(interaction: discord.Interaction, busyness: app_commands.Choice[int]):
        status = storage.update_busyness(interaction.guild_id, interaction.user.id, busyness.value)
        if status is None:
            msg = "You're not marked as available yet. Use `/available` first."
        else:
            msg = f"Updated: {describe(status.busyness)}"
        await interaction.response.send_message(msg, ephemeral=True)

    @tree.command(name="unavailable", description="Remove yourself from the availability list")
    @app_commands.guild_only()
    async def unavailable(interaction: discord.Interaction):
        removed = storage.clear_status(interaction.guild_id, interaction.user.id)
        msg = "You've been removed from the availability list." if removed \
            else "You weren't on the availability list."
        await interaction.response.send_message(msg, ephemeral=True)

    @tree.command(name="availability", description="Show available members ranked from least to most busy")
    @app_commands.guild_only()
    async def availability(interaction: discord.Interaction):
        guild = interaction.guild
        statuses = []
        for status in storage.ranked(interaction.guild_id):
            if guild.get_member(status.user_id) is None:
                try:
                    await guild.fetch_member(status.user_id)
                except discord.NotFound:
                    # Member left the server; drop their stale entry.
                    storage.clear_status(guild.id, status.user_id)
                    continue
                except discord.HTTPException:
                    pass  # keep them listed if we just can't check right now
            statuses.append(status)

        embed = discord.Embed(title="Availability", colour=discord.Colour.green())
        if not statuses:
            embed.description = "Nobody is marked as available. Use `/available` to add yourself!"
        else:
            lines = [f"**{i}.** {status_line(s)}" for i, s in enumerate(statuses[:MAX_LIST], 1)]
            embed.description = "\n".join(lines)
            if len(statuses) > MAX_LIST:
                embed.set_footer(text=f"…and {len(statuses) - MAX_LIST} more")
        await interaction.response.send_message(
            embed=embed, allowed_mentions=discord.AllowedMentions.none()
        )

    @tree.command(name="status", description="Show a member's availability")
    @app_commands.guild_only()
    @app_commands.describe(member="Member to check (defaults to you)")
    async def status(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        member = member or interaction.user
        s = storage.get_status(interaction.guild_id, member.id)
        msg = status_line(s) if s else f"{member.mention} is not marked as available."
        await interaction.response.send_message(
            msg, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set (see .env.example)")
    guild_id = os.getenv("GUILD_ID")
    storage = Storage(os.getenv("DATABASE_PATH", "availability.db"))
    bot = AvailabilityBot(storage, int(guild_id) if guild_id else None)
    bot.run(token)


if __name__ == "__main__":
    main()
