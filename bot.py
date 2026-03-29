import os
import discord
from discord.ext import commands, tasks
from discord.ui import View, Modal, TextInput, Select
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

app = Flask(__name__)
logs = []

def log(msg):
    time = datetime.datetime.now().strftime("%H:%M:%S")
    entry = f"[{time}] {msg}"
    print(entry)
    logs.append(entry)

    # limit log méret (ne zabálja a RAM-ot)
    if len(logs) > 200:
        logs.pop(0)

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
    with open(DATA_FILE, "w") as f:
        json.dump({"bots": bots_data, "pool": available_bots}, f, indent=2)

def load():
    global bots_data, available_bots
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
            bots_data = data["bots"]
            available_bots = data["pool"]
    except:
        pass

def get_free_bot():
    for b in available_bots:
        if not b["used"] and b["token"]:
            b["used"] = True
            return b
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

    r = requests.post(url, headers=headers, json={
        "owner": GITHUB_ORG,
        "name": f"dots-bot-{bot_id}",
        "private": True
    })

    return r.json()["html_url"] if r.status_code in [200, 201] else None

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

# ---------- RENDER ----------
def deploy(bot_id, repo, token):
    r = requests.post(
        "https://api.render.com/v1/services",
        headers={
            "Authorization": f"Bearer {RENDER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "type": "web_service",
            "autoDeploy": "yes",
            "serviceDetails": {
                "autoscaling": {
                    "enabled": False,
                    "criteria": {
                        "cpu": { "enabled": False },
                        "memory": { "enabled": False }
                    }
            },
            "runtime": "python",
            "envSpecificDetails": {
                "buildCommand": "pip install --upgrade pip && pip install -r requirements.txt && pip install -U discord.py",
                "startCommand": "python bot.py"
            },
            "maintenanceMode": { "enabled": False },
            "plan": "free",
            "pullRequestPreviewsEnabled": "no",
            "previews": { "generation": "off" },
            "region": "ohio"
        },
        "branch": "main",
        "envVars": [
            {
                "key": "BOT_TOKEN",
                "value": token
            }
        ],
        "repo": repo,
        "name": f"dots-bot-{bot_id}",
        "ownerId": "tea-d73btg7gi27c73d28i40"
        }
    )

    print("========== RENDER DEBUG ==========")
    print("STATUS:", r.status_code)
    print("BODY:", r.text)
    print("==================================")

def redeploy(bot_id):
    requests.post(
        f"https://api.render.com/v1/services/dots-bot-{bot_id}/deploys",
        headers={"Authorization": f"Bearer {RENDER_API_KEY}"}
    )

def delete_render(bot_id):
    requests.delete(
        f"https://api.render.com/v1/services/dots-bot-{bot_id}",
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
        global bot_counter
        free = get_free_bot()
        if not free:
            return await interaction.response.send_message("❌ No bots", ephemeral=True)

        bid = str(free["client_id"])  # 🔥 EZ AZ APP ID

        free = get_free_bot()
        if not free:
            return await interaction.response.send_message("❌ No bots", ephemeral=True)

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

        save()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(embed=discord.Embed(title=f"Deploy {bid}"), view=DoneView(bid))

        await interaction.response.send_message(f"🚀 Created (ID: {bid})", ephemeral=True)

class EditBotModal(Modal, title="Edit Bot"):
    bot_id = TextInput(label="BotID")
    password = TextInput(label="Password")
    name = TextInput(label="New name", required=False)

    async def on_submit(self, interaction):
        bid = self.bot_id.value

        if bid not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bid]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        if self.name.value:
            bots_data[bid]["name"] = self.name.value

        save()
        await interaction.response.send_message("✅ Updated!", ephemeral=True)

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
            print(f"🔓 Bot {client_id} released back to pool")
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
class DoneView(View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id

    @discord.ui.button(label="Deploy", style=discord.ButtonStyle.success)
    async def done(self, interaction, button):
        bid = str(self.bot_id)
        data = bots_data[bid]

        repo = create_repo_from_template(bid)

        deploy(bid, repo, data["token"])

        data["status"] = "live"
        save()

        await bot.tree.sync()
        await interaction.response.send_message("✅ LIVE!", ephemeral=True)

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
    for b in available_bots:
        if str(b["client_id"]) == str(bot_id):

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

# ---------- MENU ----------
class Menu(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="New Bot", style=discord.ButtonStyle.success)
    async def new(self, interaction, button):
        await interaction.response.send_modal(NewBotModal())

    @discord.ui.button(label="Edit Bot", style=discord.ButtonStyle.primary)
    async def edit(self, interaction, button):
        await interaction.response.send_modal(EditBotModal())

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

    print("READY")

bot.run(DISCORD_TOKEN)
