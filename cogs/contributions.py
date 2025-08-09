from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands

from services.contributions_service import ContributionService
from storage.json_store import JsonContributionStore
from utils.embeds import (
    build_leaderboard_embed,
    build_points_delta_embed,
    build_role_award_embed,
    build_points_summary_embed,
)


TIMESPAN_CHOICES = [
    app_commands.Choice(name="7 days", value="7d"),
    app_commands.Choice(name="30 days", value="30d"),
    app_commands.Choice(name="All time", value="all"),
]


class Contributions(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.store = JsonContributionStore()
        self.service = ContributionService(self.store)
        self._ready = False

    async def cog_load(self) -> None:
        await self.store.initialize()
        await self.service.initialize()
        self._ready = True

    # -------------- Utility -----------------
    @staticmethod
    def _compute_since_ts(timespan: Optional[str]) -> Optional[int]:
        if not timespan or timespan == "all":
            return None
        now = datetime.now(timezone.utc)
        if timespan == "7d":
            return int((now - timedelta(days=7)).timestamp())
        if timespan == "30d":
            return int((now - timedelta(days=30)).timestamp())
        return None

    # -------------- Commands ----------------
    @commands.hybrid_command(name="givepoints", description="Give contribution points to a user.")
    @commands.is_owner()
    @app_commands.describe(user="Member to award", amount="Positive number of points", reason="Optional reason")
    async def givepoints(
        self,
        ctx: commands.Context,
        user: discord.Member,
        amount: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        if amount <= 0:
            await ctx.reply("Amount must be a positive integer.")
            return
        assert ctx.guild is not None
        await self.service.award_points(
            guild_id=ctx.guild.id,
            user_id=user.id,
            amount=amount,
            reason=reason or "No reason provided",
            issuer_id=ctx.author.id,
        )
        embed = build_points_delta_embed(
            title="Contribution Points Awarded",
            target_display=user.mention,
            amount=amount,
            reason=reason or "No reason provided",
            issuer=ctx.author,
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="removepoints", description="Remove contribution points from a user.")
    @commands.is_owner()
    @app_commands.describe(user="Member to deduct from", amount="Positive number of points", reason="Optional reason")
    async def removepoints(
        self,
        ctx: commands.Context,
        user: discord.Member,
        amount: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        if amount <= 0:
            await ctx.reply("Amount must be a positive integer.")
            return
        assert ctx.guild is not None
        await self.service.award_points(
            guild_id=ctx.guild.id,
            user_id=user.id,
            amount=-amount,
            reason=reason or "No reason provided",
            issuer_id=ctx.author.id,
        )
        embed = build_points_delta_embed(
            title="Contribution Points Removed",
            target_display=user.mention,
            amount=-amount,
            reason=reason or "No reason provided",
            issuer=ctx.author,
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="giverolepoints", description="Give contribution points to all members of a role.")
    @commands.is_owner()
    @app_commands.describe(role="Role to award", points="Positive number of points per member", reason="Optional reason")
    async def giverolepoints(
        self,
        ctx: commands.Context,
        role: discord.Role,
        points: int,
        *,
        reason: Optional[str] = None,
    ) -> None:
        if points <= 0:
            await ctx.reply("Points must be a positive integer.")
            return
        assert ctx.guild is not None
        members: List[discord.Member] = [m for m in role.members if not m.bot]
        if not members:
            await ctx.reply("No non-bot members found in that role.")
            return
        for member in members:
            await self.service.award_points(
                guild_id=ctx.guild.id,
                user_id=member.id,
                amount=points,
                reason=reason or f"Awarded to role {role.name}",
                issuer_id=ctx.author.id,
            )
        embed = build_role_award_embed(
            role=role,
            amount=points,
            affected_count=len(members),
            reason=reason or f"Awarded to role {role.name}",
            issuer=ctx.author,
        )
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="leaderboard", description="Show the contribution leaderboard.")
    @app_commands.describe(timespan="7d, 30d, or all")
    @app_commands.choices(timespan=TIMESPAN_CHOICES)
    async def leaderboard(
        self,
        ctx: commands.Context,
        *,
        timespan: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        assert ctx.guild is not None
        span_value = timespan.value if timespan else "all"
        since = self._compute_since_ts(span_value)
        lb = await self.store.get_leaderboard(guild_id=ctx.guild.id, since_ts=since, limit=10)
        display_entries = []
        for user_id, total in lb:
            member = ctx.guild.get_member(user_id)
            display_entries.append((member, total))
        title = f"Leaderboard ({'All time' if since is None else span_value})"
        embed = build_leaderboard_embed(title=title, entries=display_entries)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="points", description="Check contribution points for yourself or another member.")
    @app_commands.describe(user="Member to check (defaults to yourself)", timespan="7d, 30d, or all")
    @app_commands.choices(timespan=TIMESPAN_CHOICES)
    async def points(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None,
        *,
        timespan: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        assert ctx.guild is not None
        target: discord.Member | None = user or (ctx.author if isinstance(ctx.author, discord.Member) else None)
        if target is None:
            await ctx.reply("Could not resolve the target member.")
            return
        span_value = timespan.value if timespan else "all"
        since = self._compute_since_ts(span_value)
        total = await self.store.get_user_total(guild_id=ctx.guild.id, user_id=target.id, since_ts=since)
        label = "All time" if since is None else span_value
        embed = build_points_summary_embed(member=target, total_points=total, timespan_label=label)
        await ctx.reply(embed=embed)

    # -------------- Error handling ----------------
    async def cog_command_error(self, ctx: commands.Context, error: Exception) -> None:
        original = getattr(error, "original", error)
        if isinstance(original, commands.MissingRequiredArgument):
            await ctx.reply(f"Missing argument: {original.param.name}")
            return
        if isinstance(original, commands.BadArgument):
            await ctx.reply("One or more arguments are invalid.")
            return
        if isinstance(original, commands.CheckFailure):
            await ctx.reply("You don't have permission to use this command.")
            return
        await ctx.reply("An unexpected error occurred while processing the command.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Contributions(bot))