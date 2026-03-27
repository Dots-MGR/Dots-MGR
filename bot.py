import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput
import requests

# -------------------------------
# TOKENS
# -------------------------------
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
DISCORD_TOKEN = os.environ.get('DISCORD_TOKEN')
ADMIN_USER_ID = 837680779072110593
GITHUB_ORG = "Dots-MGR"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# -------------------------------
# BOT ADAT TÁROLÁS
# -------------------------------
bots_data = {}  # user_id -> bot data dict

# -------------------------------
# HELPER: GitHub Issue
# -------------------------------
def create_github_issue(repo_name, title, body):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/issues"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {"title": title, "body": body}
    r = requests.post(url, headers=headers, json=data)
    if r.status_code == 201:
        return r.json()['number']  # issue number
    else:
        print(f"GitHub issue creation failed: {r.text}")
        return None

def close_github_issue(repo_name, issue_number):
    url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/issues/{issue_number}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    data = {"state": "closed"}
    r = requests.patch(url, headers=headers, json=data)
    if r.status_code == 200:
        print(f"Issue #{issue_number} closed successfully")
    else:
        print(f"Failed to close issue #{issue_number}: {r.text}")

# -------------------------------
# ADMIN ACTION VIEW
# -------------------------------
class AdminActionView(View):
    def __init__(self, user_id, action_type, repo_name, issue_number=None):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.action_type = action_type
        self.repo_name = repo_name
        self.issue_number = issue_number

    @discord.ui.button(label="Kész", style=discord.ButtonStyle.success, custom_id="mark_done")
    async def mark_done(self, button: Button, interaction: discord.Interaction):
        # Update status
        bots_data[self.user_id]['status'] = "done"
        
        # Update embed
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title += " ✅"
        await interaction.message.edit(embed=embed, view=None)

        # Notify user
        user = await bot.fetch_user(int(self.user_id))
        await user.send(f"✅ Your request for **{self.action_type}** is completed!")

        # GitHub issue close
        if self.issue_number:
            close_github_issue(self.repo_name, self.issue_number)

# -------------------------------
# MODALOK
# -------------------------------
class NewBotModal(Modal):
    def __init__(self):
        super().__init__(title="New bot form")
        self.bot_name = TextInput(label="Bot name", style=discord.TextStyle.short, min_length=2, max_length=32)
        self.bot_description = TextInput(label="Bot description", style=discord.TextStyle.paragraph, max_length=400)
        self.bot_tags = TextInput(label="Bot tags (Max 5, separated by ,)", style=discord.TextStyle.short, max_length=4000)
        self.bot_pass = TextInput(label="Access password", style=discord.TextStyle.short, min_length=8, max_length=100)
        self.add_item(self.bot_name)
        self.add_item(self.bot_description)
        self.add_item(self.bot_tags)
        self.add_item(self.bot_pass)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        bot_id = self.bot_name.value.replace(" ", "_")
        bots_data[user_id] = {
            'bot_id': bot_id,
            'token': self.bot_pass.value,
            'name': self.bot_name.value,
            'description': self.bot_description.value,
            'tags': self.bot_tags.value,
            'status': 'pending',
            'repo_url': f"https://github.com/{GITHUB_ORG}/{bot_id}"
        }

        # GitHub issue
        issue_number = create_github_issue(bot_id, f"New bot request: {self.bot_name.value}", "Review bot creation")
        bots_data[user_id]['issue_number'] = issue_number

        # Admin DM
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        embed = discord.Embed(title="New Bot Created", color=discord.Color.orange())
        embed.add_field(name="Name", value=self.bot_name.value, inline=False)
        embed.add_field(name="Description", value=self.bot_description.value, inline=False)
        embed.add_field(name="Tags", value=self.bot_tags.value, inline=False)
        embed.add_field(name="Pass", value=self.bot_pass.value, inline=False)
        embed.add_field(name="Repo", value=bots_data[user_id]['repo_url'], inline=False)
        view = AdminActionView(user_id, "create", bot_id, issue_number)
        await admin_user.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Bot created and pending admin approval.", ephemeral=True)

class EditBotModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Edit bot form")
        self.user_id = user_id
        self.bot_name = TextInput(label="Bot name", style=discord.TextStyle.short, min_length=2, max_length=32, default=bots_data[user_id]['name'])
        self.bot_description = TextInput(label="Bot description", style=discord.TextStyle.paragraph, max_length=400, default=bots_data[user_id]['description'])
        self.bot_tags = TextInput(label="Bot tags (Max 5, separated by ,)", style=discord.TextStyle.short, max_length=4000, default=bots_data[user_id]['tags'])
        self.add_item(self.bot_name)
        self.add_item(self.bot_description)
        self.add_item(self.bot_tags)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        bots_data[user_id]['name'] = self.bot_name.value
        bots_data[user_id]['description'] = self.bot_description.value
        bots_data[user_id]['tags'] = self.bot_tags.value
        bots_data[user_id]['status'] = "pending"

        # GitHub issue
        issue_number = create_github_issue(bots_data[user_id]['bot_id'], f"Edit bot request: {self.bot_name.value}", "Review bot edit")
        bots_data[user_id]['issue_number'] = issue_number

        # Admin DM
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        embed = discord.Embed(title="Edit Bot Request", color=discord.Color.blue())
        embed.add_field(name="Name", value=self.bot_name.value, inline=False)
        embed.add_field(name="Description", value=self.bot_description.value, inline=False)
        embed.add_field(name="Tags", value=self.bot_tags.value, inline=False)
        view = AdminActionView(user_id, "edit", bots_data[user_id]['bot_id'], issue_number)
        await admin_user.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Bot edit request submitted.", ephemeral=True)

class DeleteBotModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Delete bot")
        self.user_id = user_id
        self.bot_id_input = TextInput(label="Bot ID", style=discord.TextStyle.short, default=bots_data[user_id]['bot_id'])
        self.add_item(self.bot_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        bot_id = self.bot_id_input.value
        bots_data[user_id]['status'] = "pending"

        # GitHub issue
        issue_number = create_github_issue(bot_id, f"Delete bot request: {bot_id}", "Review bot deletion")
        bots_data[user_id]['issue_number'] = issue_number

        # Admin DM
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        embed = discord.Embed(title="Delete Bot Request", color=discord.Color.red())
        embed.add_field(name="Bot ID", value=bot_id, inline=False)
        view = AdminActionView(user_id, "delete", bot_id, issue_number)
        await admin_user.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Bot delete request submitted.", ephemeral=True)

class PasswordUpdateModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Update bot password")
        self.user_id = user_id
        self.bot_pass_input = TextInput(label="New Access Password", style=discord.TextStyle.short, min_length=8, max_length=100)
        self.add_item(self.bot_pass_input)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = self.user_id
        bots_data[user_id]['token'] = self.bot_pass_input.value
        bots_data[user_id]['status'] = "pending"

        # GitHub issue
        issue_number = create_github_issue(bots_data[user_id]['bot_id'], f"Password update request: {bots_data[user_id]['bot_id']}", "Review password update")
        bots_data[user_id]['issue_number'] = issue_number

        # Admin DM
        admin_user = await bot.fetch_user(ADMIN_USER_ID)
        embed = discord.Embed(title="Password Update Request", color=discord.Color.purple())
        embed.add_field(name="Bot ID", value=bots_data[user_id]['bot_id'], inline=False)
        view = AdminActionView(user_id, "password update", bots_data[user_id]['bot_id'], issue_number)
        await admin_user.send(embed=embed, view=view)

        await interaction.response.send_message("✅ Bot password update request submitted.", ephemeral=True)

# -------------------------------
# BotManagerView + gombok
# -------------------------------
class BotManagerView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id

    @discord.ui.button(label="New bot", style=discord.ButtonStyle.success, custom_id="New_Bot")
    async def new_bot(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(NewBotModal())

    @discord.ui.button(label="Edit bot", style=discord.ButtonStyle.primary, custom_id="Edit_Bot")
    async def edit_bot(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(EditBotModal(self.user_id))

    @discord.ui.button(label="Delete bot", style=discord.ButtonStyle.danger, custom_id="Del_Bot")
    async def delete_bot(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(DeleteBotModal(self.user_id))

    @discord.ui.button(label="Update password", style=discord.ButtonStyle.secondary, custom_id="Update_Pass")
    async def update_pass(self, button: Button, interaction: discord.Interaction):
        await interaction.response.send_modal(PasswordUpdateModal(self.user_id))

# -------------------------------
# SLASH COMMANDS
# -------------------------------
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Bot ready: {bot.user}")

@bot.tree.command(name="getStarted", description="Open the bot management menu")
async def get_started(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    view = BotManagerView(user_id)
    await interaction.response.send_message("Choose an action:", view=view, ephemeral=True)

# -------------------------------
# ON MESSAGE (Hi trigger)
# -------------------------------
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return
    if message.content.lower() == "hi":
        await message.channel.send(f"Hi {message.author.name}! Type `/getStarted` to begin!")
    await bot.process_commands(message)

# -------------------------------
# RUN BOT
# -------------------------------
bot.run(DISCORD_TOKEN)
