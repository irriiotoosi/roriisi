from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import settings
from domain.ranks import Rank, get_member_current_rank
from domain.shop import ShopItem, get_item_by_key, items_sorted_by_cost
from services.shop_service import ShopService


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


class PagedShopView(discord.ui.View):
    def __init__(self, *, author_id: int, items: List[ShopItem], timeout: float = 120.0) -> None:
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.items = items
        self.page = 0
        self.page_size = 4

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user and interaction.user.id == self.author_id

    def build_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Contribution Shop", color=discord.Color.orange())
        start = self.page * self.page_size
        end = start + self.page_size
        for item in self.items[start:end]:
            embed.add_field(
                name=f"{item.display_name} — {item.cost} CP",
                value=f"`{item.key}`",
                inline=False,
            )
        embed.set_footer(text=f"Page {self.page + 1}/{max(1, (len(self.items) + self.page_size - 1) // self.page_size)}")
        return embed

    @discord.ui.button(label="Prev", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:  # type: ignore[override]
        max_page = max(0, (len(self.items) - 1) // self.page_size)
        if self.page < max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        else:
            await interaction.response.defer()


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = ShopService()
        self.expiry_sweeper.start()

    async def cog_load(self) -> None:
        await self.service.initialize()

    async def cog_unload(self) -> None:
        self.expiry_sweeper.cancel()

    # ----- Group: /shop -----
    shop = app_commands.Group(name="shop", description="Contribution Shop")

    @shop.command(name="browse", description="Browse the Contribution Shop")
    async def shop_browse(self, interaction: discord.Interaction) -> None:
        items = items_sorted_by_cost()
        view = PagedShopView(author_id=interaction.user.id, items=items)
        await interaction.response.send_message(embed=view.build_embed(), view=view)

    @shop.command(name="buy", description="Buy a single-use item by key")
    @app_commands.describe(item_key="The copyable key shown in the shop list")
    async def shop_buy(self, interaction: discord.Interaction, item_key: str) -> None:
        assert interaction.guild is not None
        item = get_item_by_key(item_key)
        if item is None:
            await interaction.response.send_message("Unknown item.", ephemeral=True)
            return
        try:
            await self.service.buy(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=item.key)
        except ValueError as ve:
            code = str(ve)
            if code == "insufficient_points":
                await interaction.response.send_message("Insufficient Contribution Points for this purchase.", ephemeral=True)
                return
            await interaction.response.send_message("Unknown item.", ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("Purchase failed due to an unexpected error.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"Purchased {item.display_name}. Use it with `/item use_{item.key}`.")

    # ----- Group: /item -----
    item = app_commands.Group(name="item", description="Item info and activation")

    @item.command(name="info", description="Show item info")
    @app_commands.describe(item_key="Copyable key from the shop list")
    async def item_info(self, interaction: discord.Interaction, item_key: str) -> None:
        item = get_item_by_key(item_key)
        if item is None:
            await interaction.response.send_message("Unknown item.", ephemeral=True)
            return
        embed = discord.Embed(title=f"{item.display_name} — {item.cost} CP", description=item.description, color=discord.Color.orange())
        await interaction.response.send_message(embed=embed)

    # ---------- Specific Use Subcommands ----------
    @item.command(name="use_rainbow_spirit_ink", description="Use Rainbow Spirit Ink: set a custom name color for one week")
    @app_commands.describe(hex="Hex color like #FFAA00")
    async def use_rainbow_spirit_ink(self, interaction: discord.Interaction, hex: str) -> None:  # noqa: A002
        assert interaction.guild is not None
        key = "rainbow_spirit_ink"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_rainbow_ink(interaction, hex_color=hex)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to create or assign roles.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_five_elements_silence_seal", description="Use Five Elements Silence Seal: timeout a user for 15 minutes")
    @app_commands.describe(user="Target user (at most Elite Disciple)")
    async def use_five_elements_silence_seal(self, interaction: discord.Interaction, user: discord.Member) -> None:
        assert interaction.guild is not None
        key = "five_elements_silence_seal"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_silence_seal(interaction, target=user)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to timeout the target.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_thousand_faces_mask", description="Use Thousand Faces Mask: change a user's nickname for one hour")
    @app_commands.describe(user="Target user (not dev or Elder)", nickname="Temporary nickname")
    async def use_thousand_faces_mask(self, interaction: discord.Interaction, user: discord.Member, nickname: str) -> None:
        assert interaction.guild is not None
        key = "thousand_faces_mask"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_mask(interaction, target=user, nickname=nickname)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to change nicknames.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_temporal_stagnation_field", description="Use Temporal Stagnation Field: set 1m slowmode for 20 minutes")
    @app_commands.describe(channel="Channel to affect")
    async def use_temporal_stagnation_field(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        assert interaction.guild is not None
        key = "temporal_stagnation_field"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_slowmode(interaction, channel=channel)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to edit the channel.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_decree_of_bestowal", description="Use Decree of Bestowal: grant a temporary role for one week")
    @app_commands.describe(user="Recipient", rolename="Role name", hex="Hex color like #00FFAA")
    async def use_decree_of_bestowal(self, interaction: discord.Interaction, user: discord.Member, rolename: str, hex: str) -> None:  # noqa: A002
        assert interaction.guild is not None
        key = "decree_of_bestowal"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_bestowal(interaction, target=user, role_name=rolename, hex_color=hex)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to manage roles.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_gift_of_spiritual_transference", description="Use Gift of Spiritual Transference: grant 100 CP to a disciple (Inner/Core)")
    @app_commands.describe(user="Recipient user")
    async def use_gift_of_spiritual_transference(self, interaction: discord.Interaction, user: discord.Member) -> None:
        assert interaction.guild is not None
        key = "gift_of_spiritual_transference"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_transfer(interaction, recipient=user)
        except discord.Forbidden:
            await interaction.response.send_message("Action failed due to missing permissions.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_domain_usurpation_edict", description="Use Domain Usurpation Edict: temporarily rename a channel for one hour")
    @app_commands.describe(channel="Channel to usurp", new_name="Temporary channel name")
    async def use_domain_usurpation_edict(self, interaction: discord.Interaction, channel: discord.TextChannel, new_name: str) -> None:
        assert interaction.guild is not None
        key = "domain_usurpation_edict"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_usurpation(interaction, channel=channel, new_name=new_name)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to edit the channel.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    @item.command(name="use_whispering_realm_mirror", description="Use Whispering Realm Mirror: create a 24h temporary channel in Gremlins category")
    @app_commands.describe(channelname="New channel name")
    async def use_whispering_realm_mirror(self, interaction: discord.Interaction, channelname: str) -> None:
        assert interaction.guild is not None
        key = "whispering_realm_mirror"
        if not await self.service.has_item(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key):
            await interaction.response.send_message("You do not own this item.", ephemeral=True)
            return
        try:
            await self._use_mirror(interaction, channel_name=channelname)
        except discord.Forbidden:
            await interaction.response.send_message("I lack permissions to create channels.", ephemeral=True)
            return
        await self.service.consume(guild_id=interaction.guild.id, user_id=interaction.user.id, item_key=key)

    # ----- Effect implementations -----
    async def _use_rainbow_ink(self, interaction: discord.Interaction, *, hex_color: Optional[str]) -> None:
        assert interaction.guild is not None
        if hex_color is None or not hex_color.startswith("#") or len(hex_color) not in (7, 4):
            await interaction.response.send_message("Provide a valid hex color like #FF00AA.", ephemeral=True)
            return
        color = discord.Color(int(hex_color.replace("#", ""), 16))
        role = await interaction.guild.create_role(name=f"color-{interaction.user.id}", color=color, hoist=False, mentionable=False, permissions=discord.Permissions.none(), reason="Rainbow Spirit Ink")
        member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return
        await member.add_roles(role, reason="Rainbow Spirit Ink")
        # Record expiry in 7 days (1 week)
        expiry = _now_ts() + 7 * 24 * 3600
        await self.service.store.add_effect(interaction.guild.id, {"type": "color_role", "user_id": member.id, "role_id": role.id, "expires_at": expiry})
        await interaction.response.send_message("Applied color role for one week.")

    async def _use_silence_seal(self, interaction: discord.Interaction, *, target: discord.Member) -> None:
        assert interaction.guild is not None
        # rank restriction: cannot be dev or above Elite Disciple
        developer_role_name = settings.DEVELOPER_ROLE_NAME
        target_rank = get_member_current_rank(target)
        if developer_role_name and discord.utils.get(target.roles, name=developer_role_name):
            await interaction.response.send_message("Target is protected (developer).", ephemeral=True)
            return
        if target_rank and target_rank.name not in ("Outer Disciple", "Inner Disciple", "Core Disciple", "Elite Disciple"):
            await interaction.response.send_message("Target must be at most Elite Disciple.", ephemeral=True)
            return
        duration = timedelta(minutes=15)
        # Positional-only argument for 'until'
        await target.timeout(discord.utils.utcnow() + duration, reason="Five Elements Silence Seal")
        # Announce
        channel = discord.utils.get(interaction.guild.text_channels, name=settings.SEAL_ANNOUNCE_CHANNEL_NAME)
        content = f"{interaction.user.mention} has sealed {target.mention} for 15 minutes."
        if channel:
            await channel.send(content)
        else:
            await interaction.channel.send(content)  # type: ignore[union-attr]
        await interaction.response.send_message("Seal applied.", ephemeral=True)

    async def _use_mask(self, interaction: discord.Interaction, *, target: discord.Member, nickname: str) -> None:
        assert interaction.guild is not None
        # restriction: cannot be dev or Elder
        developer_role_name = settings.DEVELOPER_ROLE_NAME
        if developer_role_name and discord.utils.get(target.roles, name=developer_role_name):
            await interaction.response.send_message("Target is protected (developer).", ephemeral=True)
            return
        target_rank = get_member_current_rank(target)
        if target_rank and target_rank.name.lower() == "elder":
            await interaction.response.send_message("Cannot target an Elder.", ephemeral=True)
            return
        before = target.nick
        await target.edit(nick=nickname, reason="Thousand Faces Mask")
        expiry = _now_ts() + 3600
        await self.service.store.add_effect(interaction.guild.id, {"type": "nickname", "user_id": target.id, "old_nick": before, "expires_at": expiry})
        await interaction.response.send_message("Nickname changed for one hour.")

    async def _use_slowmode(self, interaction: discord.Interaction, *, channel: discord.TextChannel) -> None:
        before = channel.slowmode_delay
        await channel.edit(slowmode_delay=60, reason="Temporal Stagnation Field")
        expiry = _now_ts() + 20 * 60
        await self.service.store.add_effect(channel.guild.id, {"type": "slowmode", "channel_id": channel.id, "old_delay": before, "expires_at": expiry})
        await channel.send("Temporal Stagnation Field activated: 1m slowmode for 20 minutes.")
        await interaction.response.send_message("Slowmode set for 20 minutes.", ephemeral=True)

    async def _use_bestowal(self, interaction: discord.Interaction, *, target: discord.Member, role_name: str, hex_color: str) -> None:
        assert interaction.guild is not None
        if not hex_color.startswith("#"):
            await interaction.response.send_message("Provide a valid hex color like #00FF00.", ephemeral=True)
            return
        color = discord.Color(int(hex_color.replace("#", ""), 16))
        role = await interaction.guild.create_role(name=role_name[:96], color=color, hoist=False, mentionable=False, permissions=discord.Permissions.none(), reason="Decree of Bestowal")
        await target.add_roles(role, reason="Decree of Bestowal")
        expiry = _now_ts() + 7 * 24 * 3600
        await self.service.store.add_effect(interaction.guild.id, {"type": "temp_role", "user_id": target.id, "role_id": role.id, "expires_at": expiry})
        await interaction.response.send_message("Temporary role granted for one week.")

    async def _use_transfer(self, interaction: discord.Interaction, *, recipient: discord.Member) -> None:
        assert interaction.guild is not None
        # recipient must be Inner or Core
        rank = get_member_current_rank(recipient)
        if rank is None or rank.name not in ("Inner Disciple", "Core Disciple"):
            await interaction.response.send_message("Recipient must be Inner or Core Disciple.", ephemeral=True)
            return
        # Add 100 to recipient (purchase already charged at buy time)
        await self.service.contribution_service.award_points(
            guild_id=interaction.guild.id,
            user_id=recipient.id,
            amount=100,
            reason="Gift of Spiritual Transference received",
            issuer_id=interaction.user.id,
        )
        await interaction.response.send_message("Transferred 100 CP to recipient (20 CP tax was paid on purchase).")

    async def _use_usurpation(self, interaction: discord.Interaction, *, channel: discord.TextChannel, new_name: str) -> None:
        assert interaction.guild is not None
        before_name = channel.name
        before_topic = channel.topic
        await channel.edit(name=new_name[:96], topic=f"Temporarily usurped by {interaction.user.display_name}", reason="Domain Usurpation Edict")
        expiry = _now_ts() + 3600
        await self.service.store.add_effect(interaction.guild.id, {"type": "channel_usurp", "channel_id": channel.id, "old_name": before_name, "old_topic": before_topic, "expires_at": expiry})
        await channel.send(f"{interaction.user.mention} has usurped this domain for one hour.")
        await interaction.response.send_message("Channel usurped for one hour.", ephemeral=True)

    async def _use_mirror(self, interaction: discord.Interaction, *, channel_name: str) -> None:
        assert interaction.guild is not None
        category = discord.utils.get(interaction.guild.categories, name=settings.GREMLINS_CATEGORY_NAME)
        if category is None:
            await interaction.response.send_message("Gremlins category not found.", ephemeral=True)
            return
        chan = await interaction.guild.create_text_channel(name=channel_name[:96], category=category, reason="Whispering Realm Mirror")
        expiry = _now_ts() + 24 * 3600
        await self.service.store.add_effect(interaction.guild.id, {"type": "temp_channel", "channel_id": chan.id, "expires_at": expiry})
        await interaction.response.send_message(f"Created temporary channel {chan.mention} for 24 hours.")

    # ----- Expiry sweep -----
    @tasks.loop(minutes=1.0)
    async def expiry_sweeper(self) -> None:
        await self._sweep_all_guilds()

    async def _sweep_all_guilds(self) -> None:
        for guild in self.bot.guilds:
            try:
                await self._sweep_guild(guild)
            except Exception:
                continue

    async def _sweep_guild(self, guild: discord.Guild) -> None:
        effects = await self.service.store.list_effects(guild.id)
        if not effects:
            return
        now_ts = _now_ts()
        remaining: List[dict] = []
        for eff in effects:
            if int(eff.get("expires_at", 0)) > now_ts:
                remaining.append(eff)
                continue
            etype = eff.get("type")
            try:
                if etype == "slowmode":
                    channel = guild.get_channel(int(eff["channel_id"]))
                    if isinstance(channel, discord.TextChannel):
                        await channel.edit(slowmode_delay=int(eff.get("old_delay", 0)), reason="Effect expiry")
                        await channel.send("Temporal Stagnation Field ended.")
                elif etype == "temp_role" or etype == "color_role":
                    role = guild.get_role(int(eff["role_id"]))
                    user = guild.get_member(int(eff.get("user_id", 0)))
                    if user and role:
                        try:
                            await user.remove_roles(role, reason="Effect expiry")
                        except discord.Forbidden:
                            pass
                    if role:
                        try:
                            await role.delete(reason="Effect expiry")
                        except discord.Forbidden:
                            pass
                elif etype == "nickname":
                    member = guild.get_member(int(eff.get("user_id", 0)))
                    if member:
                        await member.edit(nick=eff.get("old_nick"))
                elif etype == "channel_usurp":
                    channel = guild.get_channel(int(eff["channel_id"]))
                    if isinstance(channel, discord.TextChannel):
                        await channel.edit(name=eff.get("old_name"), topic=eff.get("old_topic"))
                        await channel.send("Domain usurpation has ended.")
                elif etype == "temp_channel":
                    channel = guild.get_channel(int(eff["channel_id"]))
                    if isinstance(channel, discord.TextChannel):
                        await channel.edit(sync_permissions=True)
                        await channel.send("This channel will now be archived.")
                        try:
                            await channel.delete(reason="Effect expiry")
                        except discord.Forbidden:
                            pass
            except Exception:
                # swallow errors to avoid breaking the sweep loop
                pass
        await self.service.store.save_effects(guild.id, remaining)


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = ShopService()

    async def cog_load(self) -> None:
        await self.service.initialize()

    @commands.hybrid_command(name="inventory", description="Show your shop inventory")
    async def inventory(self, ctx: commands.Context) -> None:
        assert ctx.guild is not None
        counts = await self.service.get_inventory(guild_id=ctx.guild.id, user_id=ctx.author.id)
        if not counts:
            await ctx.reply("Your inventory is empty.")
            return
        lines: List[str] = []
        for key, count in counts.items():
            item = get_item_by_key(key)
            name = item.display_name if item else key
            lines.append(f"{name} — x{count} (key: `{key}`)")
        embed = discord.Embed(title="Your Inventory", description="\n".join(lines), color=discord.Color.orange())
        await ctx.reply(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Shop(bot))
    await bot.add_cog(Inventory(bot))