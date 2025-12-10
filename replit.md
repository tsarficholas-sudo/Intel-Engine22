# Intel-Engine Discord Bot

A Discord bot that performs comprehensive background checks on Roblox users with alt detection, ban checking, risk assessment, and color-coded reports. Includes a web server for hosting on Render with UptimeRobot monitoring.

## Overview

This bot provides Roblox user verification tools for Discord servers. It helps moderators identify potential alt accounts, banned users, and assess risk levels for new members with extensive data gathering.

## Commands

### User Commands
- `/altcheck [username]` - Check if a user is likely an alt account with detailed scoring
- `/scan [username]` - Run a comprehensive background scan with all available data
- `/export [count]` - Export recent scan history as JSON (default: 10 scans)

### Admin Commands (Require Administrator permission)
- `/addban [user_id]` - Add a Roblox user ID to the ban list
- `/removeban [user_id]` - Remove a Roblox user ID from the ban list
- `/addgroup [group_id]` - Add a group ID to the banned groups list
- `/removegroup [group_id]` - Remove a group ID from the banned groups list
- `/listbans` - List all banned user IDs and group IDs

## Risk Assessment

### Risk Levels
- **LOW** (Green) - Risk score under 20
- **MEDIUM** (Yellow) - Risk score 20-39
- **HIGH** (Red) - Risk score 40+

### Flags Checked
- Account age (very new accounts flagged)
- Custom ban list membership
- Roblox account ban status
- Follower count (low followers flagged)
- Follower/following ratio (suspicious ratios flagged)
- Friend count (low friends flagged)
- Badge count (low badges flagged)
- Description keyword scanning (exploits, cheats, etc.)
- Display name presence
- Banned group membership
- Group membership count

## Web Server Endpoints

The bot includes a Flask web server for hosting on Render:

- `GET /` - Status JSON
- `GET /health` - Health check endpoint
- `GET /ping` - Simple ping/pong for UptimeRobot

## Configuration

### Environment Variables
- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)

### Configurable Settings in main.py
- `BANNED_USERS` - List of Roblox user IDs to flag
- `BANNED_GROUPS` - List of Roblox group IDs to flag
- `FLAGGED_KEYWORDS` - Keywords to scan for in descriptions
- `NEW_ACCOUNT_DAYS` - Account age threshold (default: 14 days)
- `LOW_FOLLOWER_THRESHOLD` - Minimum followers before flagging (default: 5)
- `LOW_BADGE_THRESHOLD` - Minimum badges before flagging (default: 3)
- `LOW_FRIEND_THRESHOLD` - Minimum friends before flagging (default: 5)

## Render Deployment

1. Create a new Web Service on Render
2. Connect your GitHub/GitLab repository
3. Set build command: `pip install discord.py aiohttp flask`
4. Set start command: `python main.py`
5. Add environment variable: `DISCORD_BOT_TOKEN`
6. Deploy

## UptimeRobot Setup

1. Create account at uptimerobot.com
2. Add new monitor (HTTP(s))
3. Set URL to: `https://your-render-url.onrender.com/ping`
4. Set monitoring interval (5 minutes recommended)

## Tech Stack

- Python 3.11
- discord.py - Discord bot framework
- aiohttp - Async HTTP client for Roblox API
- Flask - Web server for health checks

## Recent Changes

- December 2024: Added comprehensive scanning with followers, badges, groups, description
- December 2024: Added Flask web server for Render hosting
- December 2024: Added export functionality
- December 2024: Added admin commands for managing ban lists
- December 2024: Removed /check and /risk commands (consolidated into /scan)
