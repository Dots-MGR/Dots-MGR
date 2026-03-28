import os
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
import json
import hashlib
import requests
import base64

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
def create_repo_from_template(bot_id):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{TEMPLATE_REPO}/generate"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    data = {
        "owner": GITHUB_ORG,
        "name": f"dots-bot-{bot_id}",
        "private": True
    }

    r = requests.post(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        return r.json()["html_url"]
    return None

def upload_config(repo_name, config_data):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/contents/config.json"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    content = json.dumps(config_data, indent=2).encode()
    encoded = base64.b64encode(content).decode()

    data = {"message": "Add config.json", "content": encoded}
    requests.put(url, headers=headers, json=data)

def update_config(repo_name, config, sha):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/contents/config.json"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}

    encoded = base64.b64encode(json.dumps(config, indent=2).encode()).decode()

    requests.put(url, headers=headers, json={
        "message": "Update commands",
        "content": encoded,
        "sha": sha
    })

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
        "buildCommand": "pip install --upgrade pip & pip install -r requirements.txt & pip install -U discord.py",
        "startCommand": "python bot.py",
        "envVars": [{"key": "BOT_TOKEN", "value": token}]
    }

    r = requests.post(url, headers=headers, json=data)
    return r.status_code in [200, 201]

def redeploy(bot_id):
    url = f"https://api.render.com/v1/services/dots-bot-{bot_id}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    requests.post(url, headers=headers)

def delete_render_service(bot_id):
    url = f"https://api.render.com/v1/services/dots-bot-{bot_id}"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    requests.delete(url, headers=headers)

# ---------- MODALS ----------
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
            "token": free["token"],
            "client_id": free["client_id"],
            "status": "pending"
        }

        save()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(
            embed=discord.Embed(title=f"Deploy Bot {bot_id}", description=self.name.value),
            view=DoneView(bot_id)
        )

        await interaction.response.send_message(f"🚀 Request sent (ID: {bot_id})", ephemeral=True)

class CommandModal(Modal, title="Add Command"):
    bot_id = TextInput(label="BotID")
    bot_pass = TextInput(label="Password")
    cmd_req = TextInput(label="Command (!hi Hello)", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction):
        bid = self.bot_id.value

        if bid not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        data = bots_data[bid]

        if data["password"] != hash_password(self.bot_pass.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        try:
            trigger, response = self.cmd_req.value.split(" ", 1)
        except:
            return await interaction.response.send_message("❌ Format: !hi Hello", ephemeral=True)

        repo = f"dots-bot-{bid}"
        url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/config.json"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        r = requests.get(url, headers=headers)
        file = r.json()
        config = json.loads(base64.b64decode(file["content"]).decode())

        config.setdefault("commands", {})
        config["commands"][trigger.lower()] = response

        update_config(repo, config, file["sha"])
        redeploy(bid)

        # Gombos szerkesztés/törlés
        await interaction.response.send_message(
            f"✅ Command '{trigger}' added & redeployed!",
            ephemeral=True,
            view=CommandView(bid, trigger)
        )

class EditCommandModal(Modal, title="Edit Command"):
    new_response = TextInput(label="New response")

    def __init__(self, bot_id, trigger):
        super().__init__()
        self.bot_id = bot_id
        self.trigger = trigger

    async def on_submit(self, interaction):
        bid = self.bot_id
        repo = f"dots-bot-{bid}"
        url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/config.json"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers)
        file = r.json()
        config = json.loads(base64.b64decode(file["content"]).decode())

        if "commands" in config and self.trigger in config["commands"]:
            config["commands"][self.trigger] = self.new_response.value
            update_config(repo, config, file["sha"])
            redeploy(bid)

        await interaction.response.send_message(f"✅ Command '{self.trigger}' updated!", ephemeral=True)

class CommandView(View):
    def __init__(self, bot_id, trigger):
        super().__init__(timeout=None)
        self.bot_id = bot_id
        self.trigger = trigger

    @discord.ui.button(label="Edit Command", style=discord.ButtonStyle.primary)
    async def edit(self, interaction, button):
        await interaction.response.send_modal(EditCommandModal(self.bot_id, self.trigger))

    @discord.ui.button(label="Delete Command", style=discord.ButtonStyle.danger)
    async def delete(self, interaction, button):
        bid = self.bot_id
        repo = f"dots-bot-{bid}"
        url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/contents/config.json"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(url, headers=headers)
        file = r.json()
        config = json.loads(base64.b64decode(file["content"]).decode())

        if "commands" in config and self.trigger in config["commands"]:
            del config["commands"][self.trigger]
            update_config(repo, config, file["sha"])
            redeploy(bid)

        await interaction.response.send_message(f"✅ Command '{self.trigger}' deleted!", ephemeral=True)

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

class DeleteBotModal(Modal, title="Delete Bot"):
    bot_id = TextInput(label="BotID")
    password = TextInput(label="Password")

    async def on_submit(self, interaction):
        bid = self.bot_id.value

        if bid not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bid]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        # Render törlése
        delete_render_service(bid)

        # GitHub repo törlése
        repo_name = f"dots-bot-{bid}"
        requests.delete(
            f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}",
            headers={"Authorization": f"token {GITHUB_TOKEN}"}
        )

        # Bot adat törlése
        del bots_data[bid]
        save()

        await interaction.response.send_message("🗑️ Deleted Render service, GitHub repo & bot data!", ephemeral=True)

# ---------- DONE ----------
class DoneView(View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id

    @discord.ui.button(label="Kész", style=discord.ButtonStyle.success)
    async def done(self, interaction, button):
        bid = str(self.bot_id)
        data = bots_data[bid]

        repo = create_repo_from_template(bid)
        if not repo:
            return await interaction.response.send_message("❌ Repo fail", ephemeral=True)

        upload_config(f"dots-bot-{bid}", {
            "name": data["name"],
            "prefix": "!",
            "owner_id": data["owner"],
            "commands": {}
        })

        deploy_to_render(bid, repo, data["token"])

        data["status"] = "live"
        save()

        await bot.tree.sync()  # auto slash sync
        await interaction.response.send_message("✅ LIVE!", ephemeral=True)

# ---------- VIEW ----------
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

# ---------- COMMANDS ----------
@bot.tree.command(name="getstarted", description="Use this to show the menu!")
async def getstarted(interaction):
    await interaction.response.send_message("Menu:", view=Menu(), ephemeral=True)

@bot.tree.command(name="cmds", description="Add, remove or modify a hosted bots commands!")
async def cmds(interaction):
    owned = [b for b in bots_data.values() if b["owner"] == interaction.user.id]
    if not owned:
        return await interaction.response.send_message("❌ No bots", ephemeral=True)

    await interaction.response.send_modal(CommandModal())

@bot.tree.command(name="help", description="Lists all commands!")
async def help_command(interaction):
    cmds = [f"/{c.name}" for c in bot.tree.get_commands()]
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

# ---------- READY ----------
@bot.event
async def on_ready():
    load()
    await bot.tree.sync()
    print("READY")

bot.run(DISCORD_TOKEN)
