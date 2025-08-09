from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class ShopItem:
    key: str  # the /item <item_name> key; unique, copyable
    display_name: str
    cost: int
    description: str


ITEMS: List[ShopItem] = [
    ShopItem(
        key="rainbow_spirit_ink",
        display_name="Rainbow Spirit Ink",
        cost=40,
        description=(
            "A single-use item that allows you to set a custom hex color for your Discord name for one week.\n"
            "Activate with: /item use rainbow_spirit_ink <hex>"
        ),
    ),
    ShopItem(
        key="gift_of_spiritual_transference",
        display_name="Gift of Spiritual Transference",
        cost=120,
        description=(
            "Permanently transfer 100 CP from your own total to another Inner or Core disciple.\n"
            "The 20 CP difference is a tax to the heavens.\n"
            "Activate with: /item use gift_of_spiritual_transference <user>"
        ),
    ),
    ShopItem(
        key="thousand_faces_mask",
        display_name="Thousand Faces Mask",
        cost=250,
        description=(
            "For one hour, change the server nickname of another user (not dev or Elder).\n"
            "They can manually revert it.\n"
            "Activate with: /item use thousand_faces_mask <user> <nickname>"
        ),
    ),
    ShopItem(
        key="whispering_realm_mirror",
        display_name="Whispering Realm Mirror",
        cost=1200,
        description=(
            "Create a public temporary channel (in the 'Gremlins' category) that lasts 24 hours.\n"
            "Activate with: /item use whispering_realm_mirror <channelname>"
        ),
    ),
    ShopItem(
        key="five_elements_silence_seal",
        display_name="Five Elements Silence Seal",
        cost=400,
        description=(
            "Apply a seal to a user (not dev or above Elite Disciple). Target is timed out for 15 minutes.\n"
            "A public announcement is posted in #get-sealed-buddy.\n"
            "Activate with: /item use five_elements_silence_seal <user>"
        ),
    ),
    ShopItem(
        key="decree_of_bestowal",
        display_name="Decree of Bestowal",
        cost=500,
        description=(
            "Grant any user a temporary, custom-named, colored role for one week.\n"
            "Activate with: /item use decree_of_bestowal <user> <rolename> <hex>"
        ),
    ),
    ShopItem(
        key="temporal_stagnation_field",
        display_name="Temporal Stagnation Field",
        cost=800,
        description=(
            "For 20 minutes, activate a 1-minute slowmode in a channel. Announces activation and deactivation.\n"
            "Activate with: /item use temporal_stagnation_field <channel>"
        ),
    ),
    ShopItem(
        key="domain_usurpation_edict",
        display_name="Domain Usurpation Edict",
        cost=2500,
        description=(
            "For one hour, temporarily rename a general channel and change its topic. Reverts after.\n"
            "Activate with: /item use domain_usurpation_edict <channel> <new_name>"
        ),
    ),
]


def get_item_by_key(key: str) -> Optional[ShopItem]:
    k = key.strip().lower()
    for item in ITEMS:
        if item.key == k:
            return item
    return None


def items_sorted_by_cost() -> List[ShopItem]:
    return sorted(ITEMS, key=lambda i: (i.cost, i.display_name.lower()))