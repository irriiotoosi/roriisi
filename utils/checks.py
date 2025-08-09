from __future__ import annotations

from typing import Callable, TypeVar

from discord.ext import commands

from domain.ranks import get_member_current_rank, get_rank_by_name

T = TypeVar("T")


def is_elder() -> Callable[[T], T]:
    async def predicate(ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, commands.MemberConverter.converter):  # type: ignore[attr-defined]
            return False
        member = ctx.author  # type: ignore[assignment]
        rank = get_member_current_rank(member)
        return rank is not None and rank.name.lower() == "elder"

    return commands.check(predicate)  # type: ignore[return-value]