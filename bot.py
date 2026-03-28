import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import requests
import json
import hashlib

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "Dots-MGR/Dots-MGR"

ADMIN_ID = 837680779072110593

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# --- Storage ---
DATA_FILE = "data.json"

bots_data = {}
github_issues = {}
bot_counter = 0

# ---------- Utils ----------
def hash_password(pw: str):
    return hashlib.sha256(pw.encode()).hexdigest()

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump({
            "bots": bots_data,
            "issues": github_issues,
            "counter": bot_counter
        }, f, indent=2)

def load_data():
    global bots_data, github_issues, bot_counter
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            bots_data = data.get("bots", {})
            github_issues = data.get("issues", {})
            bot_counter = data.get("counter", 0)
    except:
        bots_data = {}
        github_issues = {}
        bot_counter = 0

def create_github_issue(title, body):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.post(url, headers=headers, json={"title": title, "body": body})
    if r.status_code == 201:
        return r.json()["number"]
    return None

def close_github_issue(issue_number):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    requests.patch(url, headers=headers, json={"state": "closed"})

# ---------- Admin Done Button ----------
class DoneView(View):
    def __init__(self, bot_id):
        super().__init__(timeout=None)
        self.bot_id = bot_id

    @discord.ui.button(label="Kész", style=discord.ButtonStyle.success)
    async def done(self, interaction: discord.Interaction, button: Button):
        bot_id = self.bot_id

        bots_data[str(bot_id)]["status"] = "done"

        issue = github_issues.get(str(bot_id))
        if issue:
            close_github_issue(issue)

        save_data()

        await interaction.message.edit(
            embed=discord.Embed(
                title=f"Bot {bot_id} completed",
                color=discord.Color.green()
            ),
            view=None
        )

        await interaction.response.send_message("✅ Done!", ephemeral=True)

# ---------- Modals ----------
class NewBotModal(Modal, title="New Bot"):
    name = TextInput(label="Name", placeholder="My bot")
    desc = TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Cool bot")
    tags = TextInput(label="Tags", placeholder="fun, utility")
    password = TextInput(label="Password", placeholder="min 8 chars")

    async def on_submit(self, interaction):
        global bot_counter
        bot_counter += 1
        bot_id = str(bot_counter)

        bots_data[bot_id] = {
            "name": self.name.value,
            "description": self.desc.value,
            "tags": self.tags.value,
            "password": hash_password(self.password.value),
            "status": "pending"
        }

        issue = create_github_issue(f"New Bot {bot_id}", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue

        save_data()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(
            embed=discord.Embed(title=f"New Bot {bot_id}", description=self.name.value),
            view=DoneView(bot_id)
        )

        await interaction.response.send_message(f"✅ Created (ID: {bot_id})", ephemeral=True)

class EditBotModal(Modal, title="Edit Bot"):
    bot_id = TextInput(label="Bot ID", placeholder="ID")
    name = TextInput(label="Name", required=False, placeholder="leave empty to keep")
    desc = TextInput(label="Description", required=False, style=discord.TextStyle.paragraph)
    tags = TextInput(label="Tags", required=False)
    password = TextInput(label="Password", placeholder="current password")

    async def on_submit(self, interaction):
        bot_id = self.bot_id.value

        if bot_id not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bot_id]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        if self.name.value:
            bots_data[bot_id]["name"] = self.name.value
        if self.desc.value:
            bots_data[bot_id]["description"] = self.desc.value
        if self.tags.value:
            bots_data[bot_id]["tags"] = self.tags.value

        bots_data[bot_id]["status"] = "pending"

        issue = create_github_issue(f"Edit Bot {bot_id}", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue

        save_data()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(
            embed=discord.Embed(title=f"Edit Bot {bot_id}"),
            view=DoneView(bot_id)
        )

        await interaction.response.send_message("✅ Edit requested", ephemeral=True)

class DeleteBotModal(Modal, title="Delete Bot"):
    bot_id = TextInput(label="Bot ID")
    password = TextInput(label="Password")

    async def on_submit(self, interaction):
        bot_id = self.bot_id.value

        if bot_id not in bots_data:
            return await interaction.response.send_message("❌ Invalid ID", ephemeral=True)

        if bots_data[bot_id]["password"] != hash_password(self.password.value):
            return await interaction.response.send_message("❌ Wrong password", ephemeral=True)

        issue = create_github_issue(f"Delete Bot {bot_id}", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue

        save_data()

        admin = await bot.fetch_user(ADMIN_ID)
        await admin.send(
            embed=discord.Embed(title=f"Delete Bot {bot_id}"),
            view=DoneView(bot_id)
        )

        await interaction.response.send_message("✅ Delete requested", ephemeral=True)

# ---------- View (FIXED BUTTONS) ----------
class BotMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="New Bot", style=discord.ButtonStyle.success)
    async def new_bot(self, interaction, button):
        await interaction.response.send_modal(NewBotModal())

    @discord.ui.button(label="Edit Bot", style=discord.ButtonStyle.primary)
    async def edit_bot(self, interaction, button):
        await interaction.response.send_modal(EditBotModal())

    @discord.ui.button(label="Delete Bot", style=discord.ButtonStyle.danger)
    async def delete_bot(self, interaction, button):
        await interaction.response.send_modal(DeleteBotModal())

# ---------- Commands ----------
@bot.tree.command(name="getstarted", description="Open menu")
async def getstarted(interaction):
    await interaction.response.send_message("Menu:", view=BotMenuView(), ephemeral=True)

@bot.command()
async def getstarted(ctx):
    await ctx.send("Menu:", view=BotMenuView())

@bot.tree.command(name="help", description="Commands list")
async def help_cmd(interaction):
    cmds = [f"/{c.name}" for c in bot.tree.get_commands()]
    await interaction.response.send_message("\n".join(cmds), ephemeral=True)

# ---------- Ready ----------
@bot.event
async def on_ready():
    load_data()
    print("Bot ready")
    await bot.tree.sync()

bot.run(DISCORD_TOKEN)
