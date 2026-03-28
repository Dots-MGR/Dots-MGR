import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
import hashlib
import requests

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
RENDER_API_KEY = os.environ.get("RENDER_API_KEY")

GITHUB_ORG = "Dots-MGR"
TEMPLATE_REPO = "bot-template"

ADMIN_ID = 837680779072110593

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

DATA_FILE = "data.json"

bots_data = {}
bot_counter = 0

# ---------- BOT POOL ----------
available_bots = [
    {"token": os.environ.get("BOT_TOKEN_1"), "client_id": os.environ.get("BOT_CLIENT_ID_1"), "used": False},
    {"token": os.environ.get("BOT_TOKEN_2"), "client_id": os.environ.get("BOT_CLIENT_ID_2"), "used": False},
]

# ---------- UTILS ----------
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def save():
    with open(DATA_FILE, "w") as f:
        json.dump({"bots": bots_data, "counter": bot_counter, "pool": available_bots}, f, indent=2)

def load():
    global bots_data, bot_counter, available_bots
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
            bots_data = data["bots"]
            bot_counter = data["counter"]
            available_bots = data["pool"]
    except:
        pass

def get_free_bot():
    for b in available_bots:
        if not b["used"] and b["token"]:
            b["used"] = True
            return b
    return None

# ---------- GITHUB ----------
def create_repo(bot_id):
    url = "https://api.github.com/orgs/{}/repos".format(GITHUB_ORG)
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    data = {
        "name": f"dots-bot-{bot_id}",
        "private": True,
        "auto_init": True
    }

    r = requests.post(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        return r.json()["html_url"]
    else:
        print("Repo error:", r.text)
        return None

# ---------- RENDER ----------
def deploy_to_render(bot_id, repo_url, token):
    url = "https://api.render.com/v1/services"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}

    data = {
        "type": "web_service",
        "name": f"dots-bot-{bot_id}",
        "repo": repo_url,
        "branch": "main",
        "runtime": "python",
        "buildCommand": "pip install -r requirements.txt",
        "startCommand": "python bot.py",
        "envVars": [{"key": "BOT_TOKEN", "value": token}]
    }

    r = requests.post(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        return r.json()
    else:
        print("Render error:", r.text)
        return None

# ---------- DONE ----------
class DoneView(View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id

    @discord.ui.button(label="Kész", style=discord.ButtonStyle.success)
    async def done(self, interaction, button):
        bot_id = str(self.bot_id)
        data = bots_data[bot_id]

        # 🔥 CREATE REPO
        repo_url = create_repo(bot_id)
        if not repo_url:
            return await interaction.response.send_message("❌ GitHub repo failed", ephemeral=True)

        # 🚀 DEPLOY
        result = deploy_to_render(bot_id, repo_url, data["token"])
        if not result:
            return await interaction.response.send_message("❌ Deploy failed", ephemeral=True)

        # 🔗 INVITE LINK
        invite = f"https://discord.com/oauth2/authorize?client_id={data['client_id']}&scope=bot&permissions=8"

        data["status"] = "live"
        data["repo"] = repo_url
        data["invite"] = invite

        save()

        # 👤 USER DM
        try:
            user = await bot.fetch_user(data["owner"])
            await user.send(
                f"🚀 Your bot **{data['name']}** is LIVE!\n\n"
                f"🔗 Invite: {invite}\n"
                f"📦 Repo: {repo_url}"
            )
        except:
            pass

        await interaction.message.edit(
            embed=discord.Embed(
                title=f"Bot {bot_id} LIVE",
                description=data["name"],
                color=discord.Color.green()
            ),
            view=None
        )

        await interaction.response.send_message("✅ FULLY DEPLOYED!", ephemeral=True)

# ---------- MODAL ----------
class NewBotModal(Modal, title="Create Bot"):
    name = TextInput(label="Bot Name", placeholder="My bot")
    desc = TextInput(label="Description", style=discord.TextStyle.paragraph)
    password = TextInput(label="Password")

    async def on_submit(self, interaction):
        global bot_counter
        bot_counter += 1
        bot_id = str(bot_counter)

        free = get_free_bot()
        if not free:
            return await interaction.response.send_message("❌ No bots available", ephemeral=True)

        bots_data[bot_id] = {
            "name": self.name.value,
            "description": self.desc.value,
            "password": hash_password(self.password.value),
            "owner": interaction.user.id,
            "status": "pending",
            "token": free["token"],
            "client_id": free["client_id"]
        }

        save()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(
            embed=discord.Embed(title=f"Deploy Bot {bot_id}", description=self.name.value),
            view=DoneView(bot_id)
        )

        await interaction.response.send_message(f"🚀 Request sent (ID: {bot_id})", ephemeral=True)

# ---------- VIEW ----------
class Menu(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="New Bot", style=discord.ButtonStyle.success)
    async def new(self, interaction, button):
        await interaction.response.send_modal(NewBotModal())

# ---------- COMMANDS ----------
@bot.tree.command(name="getstarted")
async def getstarted(interaction):
    await interaction.response.send_message("Menu:", view=Menu(), ephemeral=True)

@bot.tree.command(name="mybots")
async def mybots(interaction):
    user_id = interaction.user.id

    bots = [(bid, d) for bid, d in bots_data.items() if d["owner"] == user_id]

    if not bots:
        return await interaction.response.send_message("No bots.", ephemeral=True)

    msg = ""
    for bid, d in bots:
        msg += f"ID {bid} | {d['name']} | {d['status']}\n"

    await interaction.response.send_message(msg, ephemeral=True)

# ---------- READY ----------
@bot.event
async def on_ready():
    load()
    await bot.tree.sync()
    print("READY")

bot.run(DISCORD_TOKEN)
