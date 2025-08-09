# Contribution Bot (Discord)

A modular Discord bot for managing Contribution points using slash/hybrid commands. Designed for Replit hosting and built with Cogs, strict async I/O, and a decoupled config.

## Features
- /givepoints, /removepoints, /giverolepoints, /leaderboard, /points
- Owner-only for point issuance/removals
- JSON persistence via async storage (suitable for small servers)
- Hybrid commands (prefix + slash) with proper permission checks

## Setup (Replit)
1. Create a new Replit (Python).
2. Add files from this repo into the project.
3. In Replit Secrets, add: `DISCORD_TOKEN` with your bot token.
4. (Optional) Add `DEBUG_GUILD_ID` for faster command registration during development.
5. Ensure the bot has the following Privileged Gateway Intents enabled in the Discord Developer Portal: **Server Members Intent**.
6. Click Run. The bot will sync application commands automatically.

## Command Summary
- `/givepoints <user> <amount> [reason]` — Owner only
- `/removepoints <user> <amount> [reason]` — Owner only
- `/giverolepoints <role> <points> [reason]` — Owner only
- `/leaderboard [timespan]` — Everyone. Timespan choices: 7 days, 30 days, All time
- `/points [user] [timespan]` — Everyone. Check your own or another member’s points, with optional timespan

## Data Persistence
- Stored in `data/contributions.json`.
- For production-grade scale, replace the JSON store with a database-backed implementation that conforms to the same interface.

## Local Development
- Prefix is `!` by default.
- You can use either prefix or slash variants for the hybrid commands.