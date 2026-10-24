import os
import discord
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput, Select, Button
import json
import hashlib
import requests
import base64
import random
import itertools
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from flask import Flask, jsonify
import threading
import datetime
import asyncio

app = Flask(__name__)
logs = []

def log(msg, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] [{level}] {msg}"

    print(entry)

    with open("bot.log", "a", encoding="utf-8") as f:
        f.write(entry + "\n")

@app.route("/")
def home():
    return """
    <h1>🚧 Coming soon: Web Dashboard</h1>
    <p>This will be the control panel for your bots.</p>
    """

@app.route("/logs")
def get_logs():
    return "<br>".join(logs)

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

threading.Thread(target=run_web, daemon=True).start()

# ---------- ENV ----------
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY")

GITHUB_ORG = "Dots-MGR"
TEMPLATE_REPO = "bot-template"
ADMIN_ID = 837680779072110593

# ---------- INTENTS FIX ----------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)

DATA_FILE = "data.json"

bots_data = {}
external_bots = {}

# ---------- BOT POOL ----------
available_bots = [
    {"token": os.environ.get("BOT_TOKEN_1"), "client_id": os.environ.get("BOT_CLIENT_ID_1"), "used": False},
    {"token": os.environ.get("BOT_TOKEN_2"), "client_id": os.environ.get("BOT_CLIENT_ID_2"), "used": False},
]

# ------- Statuses -------
statuses = itertools.cycle([
    ("playing", "Running some Bots!"),
    ("watching", "How to be the best Discord Bot"),
    ("listening", "How to manage Bots"),
    ("competing", "Dev0630's toolbox!"),
    
    ("watching", "Bot uptime and status"),
    ("listening", f"{len(bot.users)} users commands"),
    ("playing", "With Python and APIs")
])

# ---------- UTILS ----------
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def save():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "bots": bots_data,
            "pool": available_bots,
            "external_bots": external_bots
        }, f, indent=2)


def load():
    global bots_data, available_bots, external_bots

    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)

        bots_data = data.get("bots", {})
        available_bots = data.get("pool", available_bots)
        external_bots = data.get("external_bots", {})

    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        log(f"Could not load data.json: {e}", "ERROR")

load()  # before any modal or command that accesses bots_data

def get_free_bot():
    log("Searching for a free bot...", "INFO")

    for b in available_bots:
        log(
            f'Checking client_id={b.get("client_id")} '
            f'used={b.get("used")} '
            f'has_token={bool(b.get("token"))}',
            "INFO"
        )

        if not b["used"] and b["token"]:
            b["used"] = True
            log(f'Allocated bot {b["client_id"]}', "INFO")
            return b

    log("No free bots found.", "WARNING")
    return None

# ---------- Loop ----------
@tasks.loop(seconds=12)
async def status_loop():
    status_type, text = next(statuses)

    if status_type == "playing":
        activity = discord.Game(name=text)

    elif status_type == "watching":
        activity = discord.Activity(type=discord.ActivityType.watching, name=text)

    elif status_type == "listening":
        activity = discord.Activity(type=discord.ActivityType.listening, name=text)

    elif status_type == "competing":
        activity = discord.Activity(type=discord.ActivityType.competing, name=text)

    await bot.change_presence(activity=activity)

# ---------- GITHUB ----------
def create_repo_from_template(bot_id):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{TEMPLATE_REPO}/generate"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    data = {
        "owner": GITHUB_ORG,
        "name": f"dots-bot-{bot_id}",
        "private": True
    }

    r = requests.post(url, headers=headers, json=data)

    log(f"GITHUB STATUS: {r.status_code}", "DEBUG")
    log(f"GITHUB RESPONSE: {r.text}", "DEBUG")

    if r.status_code in [200, 201]:
        try:
            return r.json().get("html_url")
        except:
            return f"https://github.com/{GITHUB_ORG}/dots-bot-{bot_id}"

    # 🔥 fallback (repo már lehet létezik!)
    return f"https://github.com/{GITHUB_ORG}/dots-bot-{bot_id}"

def get_config(repo):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/config.json"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    file = r.json()
    config = json.loads(base64.b64decode(file["content"]).decode())
    return config, file["sha"]

def update_config(repo, config, sha):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/config.json"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    requests.put(url, headers=headers, json={
        "message": "update config",
        "content": base64.b64encode(json.dumps(config, indent=2).encode()).decode(),
        "sha": sha
    })

def create_issue(repo_name, title, body):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/dots-bot-{bot_id}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    data = {
        "title": title,
        "body": body
    }

    r = requests.post(url, headers=headers, json=data)

    log(f"ISSUE STATUS: {r.status_code}", "DEBUG")
    log(f"ISSUE RESPONSE: {r.text}", "DEBUG")

# ---------- RENDER ----------
def deploy(bot_id, repo, token):
    payload = {
        "type": "web_service",
        "autoDeploy": "yes",
        "serviceDetails": {
            "autoscaling": {
                "enabled": False,
                "criteria": {
                    "cpu": {"enabled": False},
                    "memory": {"enabled": False}
                }
            },
            "runtime": "python",
            "envSpecificDetails": {
                "buildCommand": "pip install --upgrade pip && pip install -r requirements.txt && pip install -U discord.py",
                "startCommand": "python bot.py"
            },
            "maintenanceMode": {"enabled": False},
            "plan": "free",
            "pullRequestPreviewsEnabled": "no",
            "previews": {"generation": "off"},
            "region": "ohio"
        },
        "branch": "main",
        "envVars": [
            {"key": "BOT_TOKEN", "value": token}
        ],
        "repo": repo,
        "name": f"dots-bot-{bot_id}",
        "ownerId": "tea-d73btg7gi27c73d28i40"
    }

    r = requests.post(
        "https://api.render.com/v1/services",
        headers={
            "Authorization": f"Bearer {RENDER_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )

    log("========== RENDER DEBUG ==========", "DEBUG")
    log(f"STATUS: {r.status_code}", "DEBUG")
    log(f"BODY: {r.text}", "DEBUG")
    log("==================================", "DEBUG")

    if r.status_code in [200, 201]:
        # Save the Render service ID in bots_data
        data = r.json()
        bots_data[bot_id]["render_service_id"] = data["id"]
        save()
        return True

    return False

def redeploy(bot_id):
    requests.post(
        f"https://api.render.com/v1/services/dots-bot-{bot_id}/deploys",
        headers={"Authorization": f"Bearer {RENDER_API_KEY}"}
    )

def delete_render(bot_id):
    service_id = bots_data[bot_id].get("render_service_id")
    if service_id:
        requests.delete(
            f"https://api.render.com/v1/services/{service_id}",
            headers={"Authorization": f"Bearer {RENDER_API_KEY}"}
        )

# ---------- AI ----------
def generate_ai_command(idea):
    return random.choice([
        f"{idea}? That's interesting 🤔",
        f"I think {idea} is awesome 😎",
        f"{idea.upper()}!!! 🔥",
        f"Why {idea}? 😂"
    ])

# ---------- MODALS ----------
class NewBotModal(Modal, title="New bot form"):
    name = TextInput(label="Bot name", min_length=2, max_length=32, placeholder="A discord bot")
    desc = TextInput(label="Bot description", style=discord.TextStyle.paragraph, max_length=400, placeholder="I'm friendly!")
    tags = TextInput(label="Tags", required=False, placeholder="fun, helpful")
    password = TextInput(label="Password", min_length=8, max_length=100, placeholder="12345678")

    async def on_submit(self, interaction):
        log("NewBotModal submitted.", "INFO")

        await interaction.response.defer(ephemeral=True)
        log("Interaction deferred.", "INFO")

        try:
            log("Calling get_free_bot()...", "INFO")
            free = get_free_bot()
            log(f"get_free_bot() returned: {free}", "INFO")

            if not free:
                return await interaction.followup.send("❌ No bots", ephemeral=True)

            bid = str(free["client_id"])
            log(f"Using Bot ID: {bid}", "INFO")

            bots_data[bid] = {
                "name": self.name.value,
                "description": self.desc.value,
                "tags": self.tags.value,
                "password": hash_password(self.password.value),
                "owner": interaction.user.id,
                "token": free["token"],
                "client_id": free["client_id"],
                "status": "pending"
            }

            log("Saving data.json...", "INFO")
            save()
            log("Save complete.", "INFO")

            repo = f"dots-bot-{bid}"

            try:
                log("Creating GitHub issue...", "INFO")
                create_issue(
                    repo,
                    "🤖 Bot Created",
                    f"Bot {self.name.value} created\n"
                    f"Owner: {interaction.user}\n"
                    f"Description: {self.desc.value}\n"
                    f"Tags: {self.tags.value}"
                )
                log("GitHub issue created.", "INFO")
            except Exception as e:
                log(f"Issue error: {e}", "ERROR")

            try:
                log("Sending admin DM...", "INFO")
                admin = await bot.fetch_user(ADMIN_ID)
                await admin.send(f"Deploy {bid}")
                log("Admin DM sent.", "INFO")
            except Exception as e:
                log(f"DM error: {e}", "ERROR")

            log("Sending success followup...", "INFO")
            await interaction.followup.send(
                f"🚀 Created (ID: {bid})",
                ephemeral=True
            )
            log("Success followup sent.", "INFO")

        except Exception as e:
            log(f"MODAL CRASH: {repr(e)}", "ERROR")

            try:
                await interaction.followup.send(
                    f"❌ Error: {e}",
                    ephemeral=True
                )
            except Exception as e2:
                log(f"Failed to send error followup: {e2}", "ERROR")

class EditBotModal(Modal, title="Edit Bot"):
    name = TextInput(label="Bot name", required=False)
    desc = TextInput(label="Bot description", required=False, style=discord.TextStyle.paragraph)
    tags = TextInput(label="Tags", required=False)
    password = TextInput(label="New password (optional)", required=False, min_length=8, max_length=100)

    def __init__(self, bot_id):
        super().__init__()
        self.bot_id = bot_id

    async def on_submit(self, interaction):
        bid = self.bot_id
        bot_data = bots_data[bid]

        updates = []

        if self.name.value:
            bot_data["name"] = self.name.value
            updates.append(f"Name → {self.name.value}")
        if self.desc.value:
            bot_data["description"] = self.desc.value
            updates.append(f"Description → {self.desc.value}")
        if self.tags.value:
            bot_data["tags"] = self.tags.value
            updates.append(f"Tags → {self.tags.value}")
        if self.password.value:
            bot_data["password"] = hash_password(self.password.value)
            updates.append("Password changed")

        save()

        # GitHub issue
        repo = f"dots-bot-{bid}"
        create_issue(
            repo,
            "✏️ Bot Edited",
            "The bot was edited with the following changes:\n" + "\n".join(updates) + f"\n\nEdited by: {interaction.user}"
        )

        await interaction.response.send_message("✅ Bot updated!", ephemeral=True)

class CommandModal(Modal, title="Add Command"):
    bot_id = TextInput(label="BotID")
    password = TextInput(label="Password")
    cmd = TextInput(label="Command (!hi Hello)")
    category = TextInput(label="Category", required=False)

    async def on_submit(self, interaction):
        bid = self.bot_id.value

        if bid not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bid]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        trigger, response = self.cmd.value.split(" ", 1)

        repo = f"dots-bot-{bid}"
        config, sha = get_config(repo)

        config.setdefault("commands", {})
        config["commands"][trigger.lower()] = {
            "response": response,
            "category": self.category.value or "other"
        }

        repo = f"dots-bot-{bid}"

        create_issue(
            repo,
            "➕ Command Added",
            f"Command `{trigger}` added.\n\n"
            f"Response: {response}\n"
            f"Category: {self.category.value or 'other'}\n"
            f"By: {interaction.user}"
        )

        update_config(repo, config, sha)
        redeploy(bid)

        await interaction.response.send_message(
            f"✅ Added `{trigger}`",
            ephemeral=True,
            view=CommandView(bid, trigger)
        )

# ---------- COMMAND EDIT ----------
class CommandView(View):
    def __init__(self, bot_id, trigger):
        super().__init__(timeout=None)
        self.bot_id = bot_id
        self.trigger = trigger

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.primary)
    async def edit(self, interaction, button):
        await interaction.response.send_modal(EditCommandModal(self.bot_id, self.trigger))

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        repo = f"dots-bot-{self.bot_id}"
        config, sha = get_config(repo)
        if self.trigger in config.get("commands", {}):
            del config["commands"][self.trigger]

            repo = f"dots-bot-{self.bot_id}"

            create_issue(
                repo,
                "🗑️ Command Deleted",
                f"Command `{self.trigger}` was deleted.\n\n"
                f"By: {interaction.user}"
            )
            
            update_config(repo, config, sha)
            redeploy(self.bot_id)

        await interaction.response.send_message("🗑️ Deleted!", ephemeral=True)

class EditCommandModal(Modal, title="Edit Command"):
    new_text = TextInput(label="New response")

    def __init__(self, bot_id, trigger):
        super().__init__()
        self.bot_id = bot_id
        self.trigger = trigger

    async def on_submit(self, interaction):
        repo = f"dots-bot-{self.bot_id}"
        config, sha = get_config(repo)

        config["commands"][self.trigger]["response"] = self.new_text.value

        repo = f"dots-bot-{self.bot_id}"

        create_issue(
            repo,
            "✏️ Command Edited",
            f"Command `{self.trigger}` updated.\n\n"
            f"New response: {self.new_text.value}\n"
            f"By: {interaction.user}"
        )

        update_config(repo, config, sha)
        redeploy(self.bot_id)

        await interaction.response.send_message("✅ Updated!", ephemeral=True)

# ---------- CMD LIST ----------
class BotSelect(Select):
    def __init__(self, user_id):
        options = [
            discord.SelectOption(label=f"{b['name']} (ID: {bid})", value=bid)
            for bid, b in bots_data.items() if b["owner"] == user_id
        ]
        super().__init__(placeholder="Select bot", options=options)

    async def callback(self, interaction):
        bid = self.values[0]
        config, _ = get_config(f"dots-bot-{bid}")

        cmds = config.get("commands", {})

        if not cmds:
            return await interaction.response.send_message("❌ No commands", ephemeral=True)

        categories = {}

        for name, data in cmds.items():
            cat = data.get("category", "other")
            categories.setdefault(cat, []).append((name, data["response"]))

        msg = ""
        for cat, items in categories.items():
            msg += f"\n📁 {cat.upper()}\n"
            for name, resp in items:
                msg += f"• {name} → {resp}\n"

        await interaction.response.send_message(msg, ephemeral=True)

class BotSelectView(View):
    def __init__(self, user_id):
        super().__init__()
        self.add_item(BotSelect(user_id))

# ---------- DELETE BOT ----------
def release_bot(client_id):
    for b in available_bots:
        if str(b["client_id"]) == str(client_id):
            b["used"] = False
            log(f"🔓 Bot {client_id} released back to pool", "SUCCESS")
            return

class DeleteBotModal(Modal, title="Delete Bot"):
    bot_id = TextInput(label="BotID")
    password = TextInput(label="Password")

    async def on_submit(self, interaction):
        bid = self.bot_id.value

        if bid not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bid]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        # proceed with deletion

        delete_render(bid)

        requests.delete(
            f"https://api.github.com/repos/{GITHUB_ORG}/dots-bot-{bid}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"}
        )

        release_bot(bid)
        del bots_data[bid]
        save()

        await interaction.response.send_message("🗑️ Deleted!", ephemeral=True)
# ---------- DEPLOY ----------
class DoneView(discord.ui.View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id

    @discord.ui.button(
        label="Deploy",
        style=discord.ButtonStyle.success,
        custom_id="deploy_button"  # 🔥 IMPORTANT FIX
    )
    async def deploy(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        try:
            bid = str(self.bot_id)

            if bid not in bots_data:
                return await interaction.followup.send("❌ Bot not found!", ephemeral=True)

            data = bots_data[bid]

            repo = create_repo_from_template(bid)
            if not repo:
                return await interaction.followup.send("❌ Repo creation failed!", ephemeral=True)

            deploy(bid, repo, data["token"])

            data["status"] = "live"
            save()

            await bot.tree.sync()

            await interaction.followup.send("✅ Bot deployed successfully!", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Error: {repr(e)}", ephemeral=True)
            
# ---------- COMMANDS ----------
@bot.tree.command(name="getstarted", description="Opens the main menu")
async def getstarted(interaction):
    await interaction.response.send_message("Menu:", view=Menu(), ephemeral=True)

@bot.tree.command(name="help", description="Lists all Dots MGR commands")
async def help_command(interaction):
    cmds = [f"/{c.name} - {c.description}" for c in bot.tree.get_commands()]
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

@bot.tree.command(name="cmds", description="Create a new command for your bot")
async def cmds(interaction):
    await interaction.response.send_modal(CommandModal())

@bot.tree.command(name="cmdlist", description="View your bots commands")
async def cmdlist(interaction):
    await interaction.response.send_message("Select:", view=BotSelectView(interaction.user.id), ephemeral=True)

@bot.tree.command(name="aicmd", description="Generate a command using AI")
async def aicmd(interaction):
    class AIModal(Modal, title="AI Command"):
        bot_id = TextInput(label="BotID")
        password = TextInput(label="Password")
        trigger = TextInput(label="Trigger")
        idea = TextInput(label="Idea")

        async def on_submit(self, interaction):
            bid = self.bot_id.value

            if bots_data[bid]["password"] != hash_password(self.password.value):
                return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

            response = generate_ai_command(self.idea.value)

            repo = f"dots-bot-{bid}"
            config, sha = get_config(repo)

            config.setdefault("commands", {})
            config["commands"][self.trigger.value.lower()] = {
                "response": response,
                "category": "ai"
            }

            update_config(repo, config, sha)
            redeploy(bid)

            await interaction.response.send_message(f"🤖 {response}", ephemeral=True)

    await interaction.response.send_modal(AIModal())

@bot.tree.command(name="poolbot")
async def poolbot(interaction: discord.Interaction, bot_id: str):
    # 🔒 access check
    if interaction.user.id != 837680779072110593:
        return await interaction.response.send_message("❌ Can't use command!", ephemeral=True)

    # 🔍 keresés pool-ban
    if bot_id in bots_data:
        b = next((x for x in available_bots if x["client_id"] == bots_data[bot_id]["client_id"]), None)
        if b:
            # reset, delete, etc.
            # 🔥 Render törlés
            delete_render(bot_id)

            # 🔥 GitHub repo törlés
            requests.delete(
                f"https://api.github.com/repos/{GITHUB_ORG}/dots-bot-{bot_id}",
                headers={"Authorization": f"token {GITHUB_TOKEN}"}
            )

            # 🔓 pool reset
            b["used"] = False
            save()

            return await interaction.response.send_message(
                f"🔓 Bot {bot_id} released + cleaned!",
                ephemeral=True
            )

    await interaction.response.send_message("❌ Bot not found in pool!", ephemeral=True)

@bot.tree.command(name="resetpool")
async def resetpool(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message("❌ Can't use command!", ephemeral=True)

    reset_count = 0

    for b in available_bots:
        if b.get("used"):
            b["used"] = False
            reset_count += 1

    save()

    await interaction.response.send_message(
        f"🔄 Pool reset complete. Freed {reset_count} bots.",
        ephemeral=True
    )

# ---------- ONBOARD EXISTING BOT ----------

class OnboardBotModal(Modal, title="Import Existing Bot"):
    token = TextInput(
        label="Discord Bot Token",
        placeholder="Paste the bot token here",
        min_length=20,
        max_length=200,
        required=True
    )

    def __init__(self, bot_id: str):
        super().__init__()
        self.bot_id = bot_id

    async def on_submit(self, interaction: discord.Interaction):
        # Only the authorized administrator can import bots.
        if interaction.user.id != ADMIN_ID:
            return await interaction.response.send_message(
                "❌ You aren't authorized to import bots.",
                ephemeral=True
            )

        await interaction.response.defer(ephemeral=True)

        token = self.token.value.strip()

        # Verify the token with Discord without blocking the bot.
        try:
            response = await asyncio.to_thread(
                requests.get,
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bot {token}"},
                timeout=15
            )

            if response.status_code != 200:
                return await interaction.followup.send(
                    "❌ Discord rejected this token. Check it and try again.",
                    ephemeral=True
                )

            bot_info = response.json()

        except requests.RequestException:
            return await interaction.followup.send(
                "❌ Couldn't contact Discord to verify the bot.",
                ephemeral=True
            )

        verified_id = str(bot_info.get("id", ""))

        # Never register a different bot than the one requested.
        if verified_id != self.bot_id:
            return await interaction.followup.send(
                "❌ The token belongs to a different bot. "
                f"Verified ID: `{verified_id}`",
                ephemeral=True
            )

        if not bot_info.get("bot", False):
            return await interaction.followup.send(
                "❌ This account isn't a bot account.",
                ephemeral=True
            )

        # Prevent collisions with existing registered bots.
        if self.bot_id in bots_data or self.bot_id in external_bots:
            return await interaction.followup.send(
                "❌ This bot ID is already registered in Dots MGR.",
                ephemeral=True
            )

        # Store metadata ONLY. Never store the supplied token.
        external_bots[self.bot_id] = {
            "name": bot_info.get("username", "Unknown Bot"),
            "bot_id": self.bot_id,
            "owner_id": interaction.user.id,
            "type": "external",
            "hosting": "railway_or_other",
            "status": "imported",
            "registered_at": datetime.datetime.now(
                datetime.timezone.utc
            ).isoformat()
        }

        save()

        log(
            f"External bot registered: {self.bot_id} "
            f"by admin {interaction.user.id}",
            "INFO"
        )

        await interaction.followup.send(
            f"✅ **{discord.utils.escape_markdown(bot_info.get('username', 'Unknown Bot'))}** "
            "has been registered in Dots MGR!\n\n"
            f"**Bot ID:** `{self.bot_id}`\n"
            "**Type:** External\n"
            "**Hosting management:** Not connected\n"
            "**Token saved:** No",
            ephemeral=True
        )

@bot.tree.command(
    name="onboardbot",
    description="Register an existing Discord bot in Dots MGR"
)
async def onboardbot(
    interaction: discord.Interaction,
    bot_id: str
):
    if interaction.user.id != ADMIN_ID:
        return await interaction.response.send_message(
            "❌ You aren't authorized to use this command.",
            ephemeral=True
        )

    if not bot_id.isdigit():
        return await interaction.response.send_message(
            "❌ Enter a valid numeric Discord bot ID.",
            ephemeral=True
        )

    await interaction.response.send_modal(OnboardBotModal(bot_id))

# ---------- MENU ----------
class Menu(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="New Bot", style=discord.ButtonStyle.success)
    async def new(self, interaction, button):
        await interaction.response.send_modal(NewBotModal())

    @discord.ui.button(label="Edit Bot", style=discord.ButtonStyle.primary)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_bots = [
            (bid, data)
            for bid, data in bots_data.items()
            if int(data.get("owner", 0)) == interaction.user.id
        ]

        if not user_bots:
            return await interaction.response.send_message(
                "❌ You don't have any bots to edit.",
                ephemeral=True
            )

        if len(user_bots) == 1:
            bid, _ = user_bots[0]
            return await interaction.response.send_modal(EditBotModal(bid))

        options = [
            discord.SelectOption(
                label=data["name"][:100],
                value=bid,
                description=f"Bot ID: {bid}"[:100]
            )
            for bid, data in user_bots[:25]
        ]

        await interaction.response.send_message(
            "Select the bot you want to edit:",
            view=EditBotSelectView(options),
            ephemeral=True
        )

    @discord.ui.button(label="Delete Bot", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        await interaction.response.send_modal(DeleteBotModal())

# ---------- READY ----------
@bot.event
async def on_ready():
    load()
    await bot.tree.sync()
    
    if not status_loop.is_running():
        status_loop.start()

    log("READY", "INFO")

bot.run(DISCORD_TOKEN)
