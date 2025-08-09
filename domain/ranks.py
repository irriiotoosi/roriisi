from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import discord


@dataclass(frozen=True)
class Rank:
    name: str
    role_name: str
    cost: int
    benefits: List[str]


RANKS: List[Rank] = [
    Rank(
        name="Outer Disciple",
        role_name="Outer Disciple",
        cost=0,
        benefits=[
            "Access to general community channels.",
            "The right to earn Contribution Points .",
            "A basic \"Outer Disciple\" role in Discord.",
        ],
    ),
    Rank(
        name="Inner Disciple",
        role_name="Inner Disciple",
        cost=150,
        benefits=[
            "Access to the #inner-sanctum channel for sneak peeks and direct developer thoughts.",
            "Minor Poll Participation: Vote in exclusive polls on flavour decisions (within #inner-sanctum).",
        ],
    ),
    Rank(
        name="Core Disciple",
        role_name="Core Disciple",
        cost=500,
        benefits=[
            "The Power of Attunement: Select a 'Path' title; feedback on this Path is highlighted with priority.",
        ],
    ),
    Rank(
        name="Elite Disciple",
        role_name="Elite Disciple",
        cost=1500,
        benefits=[
            "Custom Thematic Title: Request a unique, thematic role name (subject to approval).",
            "Become a Faction Patron: Declare patronage over an in-game faction; provide direct input on lore and mechanics.",
        ],
    ),
    Rank(
        name="Elder",
        role_name="Elder",
        cost=4000,
        benefits=[
            "Immortalized in Credits under 'Council of Elders'.",
            "Propose Missions for #contribution-board (subject to approval).",
            "The Lineage Proclamation: Recognize one Protégé; they gain 250 CP and you receive 5% of their future awards.",
        ],
    ),
    Rank(
        name="Peak Master",
        role_name="Peak Master",
        cost=10000,
        benefits=[
            "Legendary Contributor Credit at the top of credits.",
            "The World Remembers: An easter egg representing your legacy is woven into the game world.",
            "The Progenitor's Philosophy: A core design principle named in your honor.",
        ],
    ),
]


def get_rank_by_name(name: str) -> Optional[Rank]:
    lname = name.lower()
    for r in RANKS:
        if r.name.lower() == lname or r.role_name.lower() == lname:
            return r
    return None


def get_member_current_rank(member: discord.Member) -> Optional[Rank]:
    # Determine by role presence, highest rank in ladder order
    member_role_names = {role.name for role in member.roles}
    last_found: Optional[Rank] = None
    for r in RANKS:
        if r.role_name in member_role_names:
            last_found = r
    return last_found


def get_next_rank(current: Optional[Rank]) -> Optional[Rank]:
    if current is None:
        return RANKS[0]
    try:
        idx = RANKS.index(current)
    except ValueError:
        return None
    if idx + 1 < len(RANKS):
        return RANKS[idx + 1]
    return None