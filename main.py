import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import datetime
import os
import json
import asyncio
import threading
from flask import Flask, jsonify

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

BANNED_USERS = [
]

BANNED_GROUPS = [
]

FLAGGED_KEYWORDS = [
    "exploit", "hack", "cheat", "scam", "free robux", "bot", "bypass",
    "executor", "script", "inject", "synapse", "krnl", "jjsploit",
    "fluxus", "arceus", "trigon", "delta", "hydrogen", "evon"
]

NEW_ACCOUNT_DAYS = 14
LOW_FOLLOWER_THRESHOLD = 5
LOW_BADGE_THRESHOLD = 3
LOW_FRIEND_THRESHOLD = 5
SUSPICIOUS_FOLLOWER_RATIO = 100

scan_history = []

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "bot": "Intel-Engine Discord Bot",
        "uptime": "running"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@app.route('/ping')
def ping():
    return "pong", 200


def run_flask():
    app.run(host='0.0.0.0', port=5000, threaded=True)


async def roblox_user_from_name(username):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://users.roblox.com/v1/usernames/users",
                json={"usernames": [username], "excludeBannedUsers": False}
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data["data"][0]["id"]
        except (KeyError, IndexError, Exception):
            return None


async def roblox_user_info(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://users.roblox.com/v1/users/{userid}") as r:
                if r.status != 200:
                    return None
                return await r.json()
        except Exception:
            return None


async def get_follower_count(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://friends.roblox.com/v1/users/{userid}/followers/count") as r:
                if r.status != 200:
                    return 0
                data = await r.json()
                return data.get("count", 0)
        except Exception:
            return 0


async def get_following_count(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://friends.roblox.com/v1/users/{userid}/followings/count") as r:
                if r.status != 200:
                    return 0
                data = await r.json()
                return data.get("count", 0)
        except Exception:
            return 0


async def get_friend_count(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://friends.roblox.com/v1/users/{userid}/friends/count") as r:
                if r.status != 200:
                    return 0
                data = await r.json()
                return data.get("count", 0)
        except Exception:
            return 0


async def get_badge_count(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://badges.roblox.com/v1/users/{userid}/badges?limit=100&sortOrder=Desc") as r:
                if r.status != 200:
                    return 0
                data = await r.json()
                return len(data.get("data", []))
        except Exception:
            return 0


async def get_user_groups(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"https://groups.roblox.com/v1/users/{userid}/groups/roles") as r:
                if r.status != 200:
                    return []
                data = await r.json()
                return data.get("data", [])
        except Exception:
            return []


async def get_user_presence(userid):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://presence.roblox.com/v1/presence/users",
                json={"userIds": [userid]}
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                presences = data.get("userPresences", [])
                return presences[0] if presences else None
        except Exception:
            return None


def risk_color(risk):
    if risk == "LOW":
        return discord.Color.green()
    if risk == "MEDIUM":
        return discord.Color.yellow()
    return discord.Color.red()


def evaluate_risk(userinfo, followers, following, friends, badges, groups, description):
    risk = "LOW"
    reasons = []
    risk_score = 0

    created = datetime.datetime.fromisoformat(userinfo["created"].replace("Z", "+00:00"))
    age_days = (datetime.datetime.now(datetime.timezone.utc) - created).days

    if age_days < 7:
        risk_score += 30
        reasons.append(f"Very new account ({age_days} days old)")
    elif age_days < NEW_ACCOUNT_DAYS:
        risk_score += 15
        reasons.append(f"New account ({age_days} days old)")

    if userinfo["id"] in BANNED_USERS:
        risk_score += 50
        reasons.append("User is in banned database")

    if userinfo.get("isBanned", False):
        risk_score += 50
        reasons.append("Account is banned on Roblox")

    if followers < LOW_FOLLOWER_THRESHOLD:
        risk_score += 10
        reasons.append(f"Very few followers ({followers})")

    if following > 0 and followers > 0:
        ratio = following / followers
        if ratio > SUSPICIOUS_FOLLOWER_RATIO:
            risk_score += 15
            reasons.append(f"Suspicious follower ratio ({following} following / {followers} followers)")

    if friends < LOW_FRIEND_THRESHOLD:
        risk_score += 10
        reasons.append(f"Very few friends ({friends})")

    if badges < LOW_BADGE_THRESHOLD:
        risk_score += 10
        reasons.append(f"Very few badges ({badges})")

    if description:
        desc_lower = description.lower()
        found_keywords = []
        for keyword in FLAGGED_KEYWORDS:
            if keyword.lower() in desc_lower:
                found_keywords.append(keyword)
        if found_keywords:
            risk_score += 25
            reasons.append(f"Flagged keywords in description: {', '.join(found_keywords)}")

    if not userinfo.get("displayName") or userinfo.get("displayName") == userinfo.get("name"):
        risk_score += 5
        reasons.append("No custom display name set")

    banned_group_ids = [g["group"]["id"] for g in groups if g["group"]["id"] in BANNED_GROUPS]
    if banned_group_ids:
        risk_score += 40
        reasons.append(f"Member of {len(banned_group_ids)} banned group(s)")

    if len(groups) == 0:
        risk_score += 5
        reasons.append("Not a member of any groups")

    if risk_score >= 40:
        risk = "HIGH"
    elif risk_score >= 20:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return risk, reasons, risk_score


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Failed to sync commands: {e}")


@bot.tree.command(name="altcheck", description="Check if a user is likely an alt account")
async def altcheck(interaction: discord.Interaction, username: str):
    await interaction.response.defer()

    userid = await roblox_user_from_name(username)
    if userid is None:
        return await interaction.followup.send("User not found.")

    userinfo = await roblox_user_info(userid)
    if userinfo is None:
        return await interaction.followup.send("Could not fetch user info.")

    followers, friends, badges = await asyncio.gather(
        get_follower_count(userid),
        get_friend_count(userid),
        get_badge_count(userid)
    )

    created = datetime.datetime.fromisoformat(userinfo["created"].replace("Z", "+00:00"))
    age_days = (datetime.datetime.now(datetime.timezone.utc) - created).days

    alt_indicators = []
    alt_score = 0

    if age_days < 7:
        alt_score += 40
        alt_indicators.append(f"Account is very new ({age_days} days)")
    elif age_days < NEW_ACCOUNT_DAYS:
        alt_score += 25
        alt_indicators.append(f"Account is new ({age_days} days)")

    if followers < LOW_FOLLOWER_THRESHOLD:
        alt_score += 20
        alt_indicators.append(f"Low followers ({followers})")

    if friends < LOW_FRIEND_THRESHOLD:
        alt_score += 20
        alt_indicators.append(f"Low friends ({friends})")

    if badges < LOW_BADGE_THRESHOLD:
        alt_score += 20
        alt_indicators.append(f"Low badges ({badges})")

    if alt_score >= 50:
        alt_status = "LIKELY ALT"
        color = discord.Color.red()
    elif alt_score >= 30:
        alt_status = "POSSIBLE ALT"
        color = discord.Color.yellow()
    else:
        alt_status = "NOT AN ALT"
        color = discord.Color.green()

    embed = discord.Embed(
        title=f"Alt Check: {userinfo['name']}",
        description=f"Alt Score: **{alt_score}/100**",
        color=color
    )
    embed.add_field(name="Alt Status", value=alt_status, inline=True)
    embed.add_field(name="Account Age", value=f"{age_days} days", inline=True)
    embed.add_field(name="Followers", value=str(followers), inline=True)
    embed.add_field(name="Friends", value=str(friends), inline=True)
    embed.add_field(name="Badges", value=str(badges), inline=True)
    embed.add_field(name="Profile", value=f"https://roblox.com/users/{userid}/profile", inline=False)

    if alt_indicators:
        embed.add_field(name="Indicators", value="\n".join(f"- {i}" for i in alt_indicators), inline=False)

    embed.set_footer(text="Intel-Engine Alt Detection")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="scan", description="Run a comprehensive background scan on a Roblox user")
async def scan(interaction: discord.Interaction, username: str):
    await interaction.response.defer()

    userid = await roblox_user_from_name(username)
    if userid is None:
        return await interaction.followup.send("User not found.")

    userinfo = await roblox_user_info(userid)
    if userinfo is None:
        return await interaction.followup.send("Could not fetch user info.")

    followers, following, friends, badges, groups, presence = await asyncio.gather(
        get_follower_count(userid),
        get_following_count(userid),
        get_friend_count(userid),
        get_badge_count(userid),
        get_user_groups(userid),
        get_user_presence(userid)
    )

    description = userinfo.get("description", "")
    risk_level, reasons, risk_score = evaluate_risk(
        userinfo, followers, following, friends, badges, groups, description
    )

    created = datetime.datetime.fromisoformat(userinfo["created"].replace("Z", "+00:00"))
    age_days = (datetime.datetime.now(datetime.timezone.utc) - created).days
    created_formatted = created.strftime("%B %d, %Y")

    last_online = "Unknown"
    if presence:
        last_online_raw = presence.get("lastOnline")
        if last_online_raw:
            try:
                last_dt = datetime.datetime.fromisoformat(last_online_raw.replace("Z", "+00:00"))
                last_online = last_dt.strftime("%B %d, %Y at %H:%M UTC")
            except Exception:
                last_online = "Unknown"

    scan_data = {
        "username": userinfo['name'],
        "display_name": userinfo.get("displayName", "N/A"),
        "user_id": userid,
        "account_age_days": age_days,
        "created": created_formatted,
        "followers": followers,
        "following": following,
        "friends": friends,
        "badges": badges,
        "groups": len(groups),
        "description": description[:200] if description else "None",
        "risk_level": risk_level,
        "risk_score": risk_score,
        "flags": reasons,
        "roblox_banned": userinfo.get("isBanned", False),
        "scanned_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scanned_by": str(interaction.user)
    }
    scan_history.append(scan_data)

    embed = discord.Embed(
        title=f"Deep Scan Report: {userinfo['name']}",
        color=risk_color(risk_level)
    )

    embed.add_field(name="User ID", value=str(userid), inline=True)
    embed.add_field(name="Display Name", value=userinfo.get("displayName", "N/A"), inline=True)
    embed.add_field(name="Account Age", value=f"{age_days} days", inline=True)

    embed.add_field(name="Created", value=created_formatted, inline=True)
    embed.add_field(name="Last Online", value=last_online, inline=True)
    embed.add_field(name="Roblox Banned", value="Yes" if userinfo.get("isBanned", False) else "No", inline=True)

    embed.add_field(name="Followers", value=str(followers), inline=True)
    embed.add_field(name="Following", value=str(following), inline=True)
    embed.add_field(name="Friends", value=str(friends), inline=True)

    embed.add_field(name="Badges", value=str(badges), inline=True)
    embed.add_field(name="Groups", value=str(len(groups)), inline=True)
    embed.add_field(name="Risk Score", value=f"{risk_score}/100", inline=True)

    embed.add_field(name="Risk Level", value=risk_level, inline=False)

    if description:
        desc_display = description[:500] + "..." if len(description) > 500 else description
        embed.add_field(name="Description", value=desc_display or "None", inline=False)

    embed.add_field(
        name="Flags",
        value="\n".join(f"- {r}" for r in reasons) if reasons else "No issues detected.",
        inline=False
    )

    embed.add_field(name="Profile", value=f"https://roblox.com/users/{userid}/profile", inline=False)

    embed.set_footer(text=f"Intel-Engine Deep Scan | Risk Score: {risk_score}/100")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="export", description="Export recent scan history as JSON")
async def export(interaction: discord.Interaction, count: int = 10):
    await interaction.response.defer(ephemeral=True)

    if not scan_history:
        return await interaction.followup.send("No scans to export yet.", ephemeral=True)

    export_data = scan_history[-count:]

    json_data = json.dumps(export_data, indent=2)

    if len(json_data) > 1900:
        filename = f"scan_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            f.write(json_data)

        await interaction.followup.send(
            f"Exported {len(export_data)} scan(s):",
            file=discord.File(filename),
            ephemeral=True
        )
        os.remove(filename)
    else:
        await interaction.followup.send(f"```json\n{json_data}\n```", ephemeral=True)


@bot.tree.command(name="addban", description="Add a Roblox user ID to the ban list")
@app_commands.default_permissions(administrator=True)
async def addban(interaction: discord.Interaction, user_id: int):
    if user_id not in BANNED_USERS:
        BANNED_USERS.append(user_id)
        await interaction.response.send_message(f"Added user ID {user_id} to ban list.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User ID {user_id} is already in ban list.", ephemeral=True)


@bot.tree.command(name="removeban", description="Remove a Roblox user ID from the ban list")
@app_commands.default_permissions(administrator=True)
async def removeban(interaction: discord.Interaction, user_id: int):
    if user_id in BANNED_USERS:
        BANNED_USERS.remove(user_id)
        await interaction.response.send_message(f"Removed user ID {user_id} from ban list.", ephemeral=True)
    else:
        await interaction.response.send_message(f"User ID {user_id} is not in ban list.", ephemeral=True)


@bot.tree.command(name="addgroup", description="Add a group ID to the banned groups list")
@app_commands.default_permissions(administrator=True)
async def addgroup(interaction: discord.Interaction, group_id: int):
    if group_id not in BANNED_GROUPS:
        BANNED_GROUPS.append(group_id)
        await interaction.response.send_message(f"Added group ID {group_id} to banned groups.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Group ID {group_id} is already banned.", ephemeral=True)


@bot.tree.command(name="removegroup", description="Remove a group ID from the banned groups list")
@app_commands.default_permissions(administrator=True)
async def removegroup(interaction: discord.Interaction, group_id: int):
    if group_id in BANNED_GROUPS:
        BANNED_GROUPS.remove(group_id)
        await interaction.response.send_message(f"Removed group ID {group_id} from banned groups.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Group ID {group_id} is not in banned groups.", ephemeral=True)


@bot.tree.command(name="listbans", description="List all banned user IDs and group IDs")
@app_commands.default_permissions(administrator=True)
async def listbans(interaction: discord.Interaction):
    embed = discord.Embed(title="Ban Lists", color=discord.Color.red())

    banned_users_text = ", ".join(str(u) for u in BANNED_USERS) if BANNED_USERS else "None"
    banned_groups_text = ", ".join(str(g) for g in BANNED_GROUPS) if BANNED_GROUPS else "None"

    embed.add_field(name="Banned User IDs", value=banned_users_text, inline=False)
    embed.add_field(name="Banned Group IDs", value=banned_groups_text, inline=False)
    embed.set_footer(text="Intel-Engine Configuration")

    await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        print("ERROR: DISCORD_BOT_TOKEN not set. Please add it to your secrets.")
    else:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        print("Flask server started on port 5000")
        bot.run(TOKEN)
