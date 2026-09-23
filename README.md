# Availability Bot

A Discord bot that lets server members say they're available and how busy they are. It can then show everyone ranked from least to most busy.

## Commands

| Command | What it does |
|---|---|
| `/available busyness:<1-5> [note]` | Mark yourself available with a busyness level (1 = totally free, 5 = swamped) and an optional note. Run it again to update your status. |
| `/busy busyness:<1-5>` | Change only your busyness level. Your note stays the same. |
| `/unavailable` | Take yourself off the list. |
| `/availability` | Show everyone who is available, least busy first. Members at the same level are ordered by who updated most recently. |
| `/status [member]` | Check one member's status (yours if no member is given). |

| Level | Meaning |
|---|---|
| 🟢 1 | Totally free |
| 🟡 2 | Mostly free |
| 🟠 3 | Somewhat busy |
| 🔴 4 | Busy |
| ⛔ 5 | Swamped |

A member's status stays until they run `/unavailable`. Statuses are stored per server in a local SQLite file, so they survive restarts.

## Setup

1. Create an application at https://discord.com/developers/applications, add a **Bot**, and copy its token.
2. Invite the bot using OAuth2 → URL Generator with the scopes `bot` and `applications.commands`. It needs the **Send Messages** and **Embed Links** permissions.
3. Install and configure:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # then put your token in DISCORD_TOKEN
   ```
   Set `GUILD_ID` to your server's ID so slash commands appear straight away. Global commands can take up to an hour to show up.
4. Run it:
   ```bash
   python bot.py
   ```

## Tests

```bash
pip install pytest
pytest
```
