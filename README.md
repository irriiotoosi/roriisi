# Contribution Bot (Discord)

A modular Discord bot for managing Contribution points using slash/hybrid commands. Designed for Replit hosting and built with Cogs, strict async I/O, and a decoupled config.

## Features
- Contribution: /givepoints, /removepoints, /giverolepoints, /leaderboard, /points
- Ranks: /rankinfo, /rankup, /status
- Lineage: Elder-only /enslave with Protégé bonus; Owner-only /entitle custom title
- Owner-only for point issuance/removals and title assignment
- JSON persistence via async storage (suitable for small servers)
- Hybrid commands (prefix + slash) with proper permission checks

## Setup (Replit)
1. Create a new Replit (Python).
2. Add files from this repo into the project.
3. In Replit Secrets, add: `DISCORD_TOKEN` with your bot token.
4. (Optional) Add `DEBUG_GUILD_ID` for faster command registration during development.
5. Enable Server Members Intent in the Discord Developer Portal.
6. Click Run. The bot will sync application commands automatically.

## Command Summary
- `/givepoints <user> <amount> [reason]` — Owner only
- `/removepoints <user> <amount> [reason]` — Owner only
- `/giverolepoints <role> <points> [reason]` — Owner only
- `/leaderboard [timespan]` — Everyone (7d, 30d, all)
- `/points [user] [timespan]` — Everyone
- `/rankinfo <rank name>` — Everyone
- `/rankup` — Everyone (uses confirmation)
- `/status [user]` — Everyone
- `/enslave <user>` — Elder only; asks target for confirmation; grants 250 CP and sets Protégé bonus (elder gains 5% on future awards)
- `/entitle <user> <title>` — Owner only

## Rank Ladder
- Outer Disciple — 0 CP (starting rank)
- Inner Disciple — 150 CP
- Core Disciple — 500 CP
- Elite Disciple — 1,500 CP
- Elder — 4,000 CP
- Peak Master — 10,000 CP

On rank up: previous rank role is removed and the new rank role is added. Ensure roles with these exact names exist in your server.

## Data Persistence
- Stored in `data/contributions.json`.
- Persists: contribution history, titles, and Elder–Protégé lineage.

## Local Development
- Prefix is `!` by default.
- You can use either prefix or slash variants for the hybrid commands.