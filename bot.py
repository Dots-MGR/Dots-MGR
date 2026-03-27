import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import requests
import json

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = "Dots-MGR/Dots-MGR"  # privát repo

ADMIN_ID = 837680779072110593

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# --- Local storage ---
bots_data = {}          # bot_id -> info
github_issues = {}      # bot_id -> GitHub issue number
bot_counter = 0

# --- Views & Modals ---
class BotMenuView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="New Bot", style=discord.ButtonStyle.success, custom_id="New_Bot"))
        self.add_item(Button(label="Edit Bot", style=discord.ButtonStyle.primary, custom_id="Edit_Bot"))
        self.add_item(Button(label="Delete Bot", style=discord.ButtonStyle.danger, custom_id="Del_Bot"))

def create_github_issue(title: str, body: str):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.post(url, headers=headers, json={"title": title, "body": body})
    if r.status_code == 201:
        return r.json()["number"]
    else:
        print(f"GitHub issue creation failed: {r.status_code} {r.text}")
        return None

def close_github_issue(issue_number: int):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/issues/{issue_number}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.patch(url, headers=headers, json={"state": "closed"})
    if r.status_code != 200:
        print(f"Failed to close issue #{issue_number}: {r.status_code} {r.text}")

class NewBotModal(Modal, title="New Bot Form"):
    bot_name = TextInput(label="Bot Name", style=discord.TextStyle.short, max_length=32)
    bot_desc = TextInput(label="Bot Description", style=discord.TextStyle.paragraph, max_length=400)
    bot_tags = TextInput(label="Bot Tags (comma separated)", style=discord.TextStyle.short)
    bot_pass = TextInput(label="Access Password", style=discord.TextStyle.short, min_length=8, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        global bot_counter
        bot_counter += 1
        bot_id = bot_counter
        bots_data[bot_id] = {
            "name": self.bot_name.value,
            "description": self.bot_desc.value,
            "tags": self.bot_tags.value,
            "password": self.bot_pass.value,
            "status": "pending"
        }
        issue_number = create_github_issue(f"New Bot Request (ID {bot_id})", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue_number

        # Admin DM
        admin = await bot.fetch_user(ADMIN_ID)
        embed = discord.Embed(title=f"New Bot Request (ID {bot_id})", color=discord.Color.orange())
        for k, v in bots_data[bot_id].items():
            embed.add_field(name=k.capitalize(), value=v, inline=False)
        view = View()
        view.add_item(Button(label="Kész", style=discord.ButtonStyle.success, custom_id=f"done_{bot_id}"))
        await admin.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Bot request submitted! (ID: {bot_id})", ephemeral=True)

class EditBotModal(Modal, title="Edit Bot Form"):
    bot_id = TextInput(label="Bot ID", style=discord.TextStyle.short)
    bot_name = TextInput(label="Bot Name", style=discord.TextStyle.short, max_length=32)
    bot_desc = TextInput(label="Bot Description", style=discord.TextStyle.paragraph, max_length=400)
    bot_tags = TextInput(label="Bot Tags (comma separated)", style=discord.TextStyle.short)
    bot_pass = TextInput(label="Access Password", style=discord.TextStyle.short, min_length=8, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        bot_id = int(self.bot_id.value)
        if bot_id not in bots_data:
            await interaction.response.send_message("❌ Invalid Bot ID", ephemeral=True)
            return

        bots_data[bot_id].update({
            "name": self.bot_name.value,
            "description": self.bot_desc.value,
            "tags": self.bot_tags.value,
            "password": self.bot_pass.value,
            "status": "pending"
        })
        issue_number = create_github_issue(f"Edit Bot Request (ID {bot_id})", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue_number

        # Admin DM
        admin = await bot.fetch_user(ADMIN_ID)
        embed = discord.Embed(title=f"Edit Bot Request (ID {bot_id})", color=discord.Color.blue())
        for k, v in bots_data[bot_id].items():
            embed.add_field(name=k.capitalize(), value=v, inline=False)
        view = View()
        view.add_item(Button(label="Kész", style=discord.ButtonStyle.success, custom_id=f"done_{bot_id}"))
        await admin.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Edit request submitted! (ID: {bot_id})", ephemeral=True)

class DeleteBotModal(Modal, title="Delete Bot Form"):
    bot_id = TextInput(label="Bot ID", style=discord.TextStyle.short)
    bot_pass = TextInput(label="Access Password", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        bot_id = int(self.bot_id.value)
        if bot_id not in bots_data:
            await interaction.response.send_message("❌ Invalid Bot ID", ephemeral=True)
            return
        if bots_data[bot_id]["password"] != self.bot_pass.value:
            await interaction.response.send_message("❌ Wrong password", ephemeral=True)
            return

        issue_number = create_github_issue(f"Delete Bot Request (ID {bot_id})", json.dumps(bots_data[bot_id], indent=2))
        github_issues[bot_id] = issue_number

        # Admin DM
        admin = await bot.fetch_user(ADMIN_ID)
        embed = discord.Embed(title=f"Delete Bot Request (ID {bot_id})", color=discord.Color.red())
        for k, v in bots_data[bot_id].items():
            embed.add_field(name=k.capitalize(), value=v, inline=False)
        view = View()
        view.add_item(Button(label="Kész", style=discord.ButtonStyle.success, custom_id=f"done_{bot_id}"))
        await admin.send(embed=embed, view=view)
        await interaction.response.send_message(f"✅ Delete request submitted! (ID: {bot_id})", ephemeral=True)

# --- Button interactions ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return
    cid = interaction.data.get("custom_id", "")
    if cid.startswith("New_Bot"):
        await interaction.response.send_modal(NewBotModal())
    elif cid.startswith("Edit_Bot"):
        await interaction.response.send_modal(EditBotModal())
    elif cid.startswith("Del_Bot"):
        await interaction.response.send_modal(DeleteBotModal())
    elif cid.startswith("done_"):
        bot_id = int(cid.split("_")[1])
        if bot_id in bots_data:
            bots_data[bot_id]["status"] = "done"
            issue_number = github_issues.get(bot_id)
            if issue_number:
                close_github_issue(issue_number)
            await interaction.message.edit(embed=discord.Embed(
                title=f"Bot ID {bot_id} - Completed",
                description="This request is now marked as done.",
                color=discord.Color.green()
            ), view=None)
            await interaction.response.send_message("Marked as done! GitHub issue closed.", ephemeral=True)

# --- Slash + Prefix commands ---
@bot.tree.command(name="getstarted", description="Open the bot management menu")
async def getstarted_slash(interaction: discord.Interaction):
    await interaction.response.send_message("Welcome! Manage your bot below:", view=BotMenuView(), ephemeral=True)

@bot.command(name="getstarted")
async def getstarted_prefix(ctx):
    await ctx.send("Welcome! Manage your bot below:", view=BotMenuView())

@bot.tree.command(name="help", description="List all Dots MGR commands")
async def help_command(interaction: discord.Interaction):
    prefix_cmds = [f"{bot.command_prefix}{c.name} - {c.help or 'No description'}" for c in bot.commands]
    slash_cmds = [f"/{c.name} - {c.description}" for c in bot.tree.get_commands()]
    message = "**Prefix commands:**\n" + "\n".join(prefix_cmds) + "\n\n**Slash commands:**\n" + "\n".join(slash_cmds)
    await interaction.response.send_message(message, ephemeral=True)

# --- Run Bot ---
@bot.event
async def on_ready():
    print(f"Bot ready: {bot.user}")
    try:
        await bot.tree.sync()
        print("Slash commands synced!")
    except Exception as e:
        print(f"Sync failed: {e}")

bot.run(DISCORD_TOKEN)
