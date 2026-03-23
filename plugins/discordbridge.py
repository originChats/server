#  ____  _                       _   _     _       _    _             
# |  _ \(_)___  ___ ___  _ __ __| | | |   (_)_ __ | | _(_)_ __   __ _ 
# | | | | / __|/ __/ _ \| '__/ _` | | |   | | '_ \| |/ / | '_ \ / _` |
# | |_| | \__ \ (_| (_) | | | (_| | | |___| | | | |   <| | | | | (_| |
# |____/|_|___/\___\___/|_|  \__,_| |_____|_|_| |_|_|\_\_|_| |_|\__, | 
#                                                               |___/  - a fries server plugin

import os
from pathlib import Path
from dotenv import load_dotenv
import asyncio
from logger import Logger
from db.webhooks import get_all_webhooks, delete_webhook, create_webhook, webhook_exists_for_channel

env_path = Path(__file__).parent / 'discordBridge.env'
load_dotenv(dotenv_path=env_path)

DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID')
DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

import discord
from discord.ext import commands
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

discord_gateway = (DISCORD_BOT_TOKEN)

directory_path = os.path.join('.', 'db', 'channels')

def channelsinit():
    global originchannels
    originchannels = []
    for entry in os.listdir(directory_path):
        full_path = os.path.join(directory_path, entry)
        if os.path.isfile(full_path):
            originchannels.append(Path(entry).stem)

channelsinit()
print(originchannels)

@bot.event
async def on_ready():
    global discordchannels
    discordchannels = []
    print(f'{bot.user} has connected to Discord!')
    print('Channels the bot can see:')
    for guild in bot.guilds:
        print(f"\nGuild: {guild.name} (ID: {guild.id})")
        for channel in guild.channels:
            Logger.info(f"- {channel.name} (Type: {channel.type}, ID: {channel.id})")
            discordchannels.append(channel.name)
    Logger.info(f"Total channels found: {len(discordchannels)}")

async def start_bot():
    await bot.start(DISCORD_BOT_TOKEN)

def init():
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())

init()