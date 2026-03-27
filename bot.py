import discord
import os
from discord import app_commands
from discord.ext import commands

TOKEN = os.environ.get('TOKEN')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.tree.command(name="ping", description="Pongs you!")
async def ping(ctx):
    await ctx.send('Pong!')

bot.run(TOKEN)
