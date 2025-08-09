from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from domain.ranks import RANKS, Rank, get_member_current_rank, get_next_rank, get_rank_by_name
from services.contributions_service import ContributionService
from storage.json_store import JsonContributionStore
from utils.embeds import build_points_summary_embed


class ConfirmView(discord.ui.View):
    def __init__(self, *, author_id: int, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.result: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user and interaction.user.id == self.author_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        self.result = True
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        self.result = False
        for child in self.children:
            child.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(view=self)
        self.stop()


class Ranks(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.store = JsonContributionStore()
        self.service = ContributionService(self.store)

    async def cog_load(self) -> None:
        await self.service.initialize()

    # ---------- Helpers ----------
    @staticmethod
    def _format_rank_embed(rank: Rank) -> discord.Embed:
        title = f"{rank.name} — {rank.cost} Contribution Points"
        embed = discord.Embed(title=title, color=discord.Color.purple())
        benefits = "\n".join(f"• {b}" for b in rank.benefits)
        embed.description = benefits
        return embed

    # ---------- Commands ----------
    @commands.hybrid_command(name="rankinfo", description="Show information about a rank")
    @app_commands.describe(name="Outer Disciple / Inner Disciple / Core Disciple / Elite Disciple / Elder / Peak Master")
    async def rankinfo(self, ctx: commands.Context, *, name: str) -> None:
        rank = get_rank_by_name(name)
        if rank is None:
            await ctx.reply("Unknown rank. Please choose a valid rank name.")
            return
        await ctx.reply(embed=self._format_rank_embed(rank))

    @commands.hybrid_command(name="status", description="Show your current rank, title and contribution points")
    @app_commands.describe(user="Member to check (defaults to yourself)")
    async def status(self, ctx: commands.Context, user: Optional[discord.Member] = None) -> None:
        assert ctx.guild is not None
        target: discord.Member | None = user or (ctx.author if isinstance(ctx.author, discord.Member) else None)
        if target is None:
            await ctx.reply("Could not resolve the target member.")
            return
        total = await self.store.get_user_total(ctx.guild.id, target.id, since_ts=None)
        current_rank = get_member_current_rank(target)
        title = await self.store.get_title(ctx.guild.id, target.id)
        rank_name = current_rank.name if current_rank else "Unranked"
        embed = discord.Embed(title=f"Status — {target.display_name}", color=discord.Color.teal())
        embed.add_field(name="Rank", value=rank_name, inline=True)
        embed.add_field(name="Contribution Points", value=str(total), inline=True)
        if title:
            embed.add_field(name="Title", value=f"✨ {title} ✨", inline=False)
        if current_rank:
            embed.add_field(name="Benefits", value="\n".join(f"• {b}" for b in current_rank.benefits), inline=False)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="rankup", description="Rank up to the next rank if you can afford it")
    async def rankup(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("This command can only be used in a server.")
            return
        member: discord.Member = ctx.author
        current = get_member_current_rank(member)
        next_rank = get_next_rank(current)
        if next_rank is None:
            await ctx.reply("You are already at the highest rank.")
            return
        total = await self.store.get_user_total(ctx.guild.id, member.id, since_ts=None)
        if total < next_rank.cost:
            await ctx.reply(f"Not enough Contribution Points. Required: {next_rank.cost}, you have: {total}.")
            return

        view = ConfirmView(author_id=member.id)
        msg = await ctx.reply(
            f"Rank up to {next_rank.name} for {next_rank.cost} points?",
            view=view,
        )
        await view.wait()
        if not view.result:
            await msg.edit(content="Rank up cancelled.", view=None)
            return

        # Deduct cost and swap roles
        await self.service.award_points(
            guild_id=ctx.guild.id,
            user_id=member.id,
            amount=-next_rank.cost,
            reason=f"Rank up to {next_rank.name}",
            issuer_id=member.id,
        )
        # Update roles: remove previous rank role, add new one
        add_role = discord.utils.get(ctx.guild.roles, name=next_rank.role_name)
        if add_role is None:
            await msg.edit(content=f"Could not find role for {next_rank.role_name}. Please set up roles.", view=None)
            return
        # Remove any rank roles from ladder
        ladder_role_names = {r.role_name for r in RANKS}
        remove_roles = [role for role in member.roles if role.name in ladder_role_names]
        try:
            await member.remove_roles(*remove_roles, reason="Rank up role change")
            await member.add_roles(add_role, reason="Rank up role change")
        except discord.Forbidden:
            await msg.edit(content="I lack permissions to modify your roles.", view=None)
            return
        await msg.edit(content=f"Congratulations! You are now {next_rank.name}.", view=None)

    # Elder-only: Protégé recognition
    @commands.hybrid_command(name="enslave", description="Elder recognizes a Protégé (below Elder); grants 250 CP and sets lineage")
    @app_commands.describe(user="Member to recognize as Protégé")
    async def enslave(self, ctx: commands.Context, user: discord.Member) -> None:
        assert ctx.guild is not None
        if not isinstance(ctx.author, discord.Member):
            await ctx.reply("This command can only be used in a server.")
            return
        elder_rank = get_member_current_rank(ctx.author)
        if elder_rank is None or elder_rank.name.lower() != "elder":
            await ctx.reply("Only Elders can use this command.")
            return
        target_rank = get_member_current_rank(user)
        if target_rank and target_rank.name.lower() == "elder":
            await ctx.reply("Target must be below Elder.")
            return
        existing = await self.store.get_protege_for_elder(ctx.guild.id, ctx.author.id)
        if existing is not None:
            await ctx.reply("You already have a Protégé set.")
            return

        view = ConfirmView(author_id=user.id)
        prompt = await ctx.reply(f"{user.mention}, do you accept becoming Protégé of {ctx.author.mention}? This grants you 250 points.", view=view)
        await view.wait()
        if not view.result:
            await prompt.edit(content="Protégé request declined.", view=None)
            return

        await self.store.set_lineage(ctx.guild.id, elder_id=ctx.author.id, protege_id=user.id)
        await self.service.award_points(
            guild_id=ctx.guild.id,
            user_id=user.id,
            amount=250,
            reason="Protégé recognition bonus",
            issuer_id=ctx.author.id,
        )
        await prompt.edit(content=f"{user.mention} is now Protégé of {ctx.author.mention}. 250 points awarded.", view=None)

    # Owner-only: entitle a user with a custom glamorous title
    @commands.hybrid_command(name="entitle", description="Owner: give a user a glamorous title shown in /status")
    @commands.is_owner()
    @app_commands.describe(user="Member to entitle", title="The glamorous title")
    async def entitle(self, ctx: commands.Context, user: discord.Member, *, title: str) -> None:
        assert ctx.guild is not None
        if not title.strip():
            await ctx.reply("Title cannot be empty.")
            return
        await self.store.set_title(ctx.guild.id, user.id, title.strip())
        await ctx.reply(f"Set title for {user.mention} to ✨ {title.strip()} ✨")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Ranks(bot))