import asyncio
import logging
import os
from typing import Optional

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import settings


logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("contrib-bot")


def _build_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = False
    # Required for role-based operations (e.g., iterating role members)
    intents.members = True
    guilds_intent = True  # default True in Intents.default()
    _ = guilds_intent  # placate linters if unused
    return intents


class ContributionBot(commands.Bot):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def setup_hook(self) -> None:
        # Load cogs
        await self.load_extension("cogs.contributions")
        await self.load_extension("cogs.ranks")

        # Optionally do a faster, guild-scoped sync in development
        debug_guild_id: Optional[int] = settings.DEBUG_GUILD_ID
        if debug_guild_id is not None:
            guild = discord.Object(id=debug_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d app commands to guild %s", len(synced), debug_guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Globally synced %d app commands", len(synced))


async def main() -> None:
    # Load from .env for local dev (Replit uses Secrets env by default)
    load_dotenv()

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable not set. Add it in Replit Secrets.")

    intents = _build_intents()

    bot = ContributionBot(
        command_prefix=settings.COMMAND_PREFIX,
        case_insensitive=True,
        intents=intents,
        help_command=None,
    )

    @bot.event
    async def on_ready() -> None:
        logger.info("Logged in as %s (%s)", bot.user, bot.user and bot.user.id)

    await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass