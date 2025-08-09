from __future__ import annotations

import discord
from typing import Iterable, Tuple


def build_points_delta_embed(
    *,
    title: str,
    target_display: str,
    amount: int,
    reason: str,
    issuer: discord.abc.User,
) -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.blurple())
    embed.add_field(name="Target", value=target_display, inline=True)
    embed.add_field(name="Amount", value=str(amount), inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_footer(text=f"Issued by {issuer} (ID: {issuer.id})")
    return embed


def build_role_award_embed(
    *,
    role: discord.Role,
    amount: int,
    affected_count: int,
    reason: str,
    issuer: discord.abc.User,
) -> discord.Embed:
    embed = discord.Embed(title="Role Contribution Award", color=discord.Color.green())
    embed.add_field(name="Role", value=role.mention, inline=True)
    embed.add_field(name="Amount per Member", value=str(amount), inline=True)
    embed.add_field(name="Members Awarded", value=str(affected_count), inline=True)
    embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
    embed.set_footer(text=f"Issued by {issuer} (ID: {issuer.id})")
    return embed


def build_leaderboard_embed(
    *,
    title: str,
    entries: Iterable[Tuple[discord.Member | None, int]],
) -> discord.Embed:
    embed = discord.Embed(title=title, color=discord.Color.gold())
    description_lines = []
    rank = 1
    for member, total in entries:
        name = member.mention if member else "<left server>"
        description_lines.append(f"**{rank}.** {name} — {total} points")
        rank += 1
    embed.description = "\n".join(description_lines) if description_lines else "No contributions yet."
    return embed