#  ____  _                       _   _     _       _    _             
# |  _ \(_)___  ___ ___  _ __ __| | | |   (_)_ __ | | _(_)_ __   __ _ 
# | | | | / __|/ __/ _ \| '__/ _` | | |   | | '_ \| |/ / | '_ \ / _` |
# | |_| | \__ \ (_| (_) | | | (_| | | |___| | | | |   <| | | | | (_| |
# |____/|_|___/\___\___/|_|  \__,_| |_____|_|_| |_|_|\_\_|_| |_|\__, | 
#                                                               |___/  - a fries server plugin

import os
import sys
import uuid
import asyncio
import time
from pathlib import Path
import gc
from discord.utils import get
from handlers.websocket_utils import broadcast_to_all, send_to_client, _get_ws_attr

def getInfo():
    return {
        "name": "DiscordBridge Plugin",
        "description": "Sends messages to/from Discord.",
        "handles": ["new_message"]
    }

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import channels
from logger import Logger
from handlers.websocket_utils import broadcast_to_all
import server

import discord
from discord.ext import commands

discordchannels = []
sharedchannels = []
originchannels = []
originwebhooks = []

env_path = Path(__file__).parent / "discordBridge.env"
load_dotenv(dotenv_path=env_path)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

directory_path = os.path.join(".", "db", "channels")

def channelsinit():
    global originchannels
    originchannels = []

    if not os.path.exists(directory_path):
        Logger.info(f"Channel directory not found: {directory_path}")
        return

    for entry in os.listdir(directory_path):
        full_path = os.path.join(directory_path, entry)
        if os.path.isfile(full_path):
            originchannels.append(Path(entry).stem)

channelsinit()

@bot.event
async def on_ready():
    global discordchannels, sharedchannels
    print(f"{bot.user} has connected to Discord!")

    for guild in bot.guilds:
        print(f"\nGuild: {guild.name} (ID: {guild.id})")
        for channel in guild.channels:
            if channel.type == discord.ChannelType.text:
                discordchannels.append(channel.name)

    Logger.info(f"Total channels found: {len(discordchannels)}")
    sharedchannels = list(set(originchannels) & set(discordchannels))

    Logger.info(f"Discord Channels: {discordchannels}")
    Logger.info(f"Origin Channels: {originchannels}")
    Logger.info(f"Shared Channels: {sharedchannels}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if not message.guild:
        return

    if message.guild.id != int(DISCORD_GUILD_ID):
        return

    if message.channel.name not in sharedchannels:
        return

    sendmessage = {
        "user": message.author.name,
        "content": "https://github.com/fries-git/saltychatsserver/blob/main/plugins/bridgeicons/discord.png?raw=true" + " " + message.content,
        "timestamp": time.time(),
        "id": str(uuid.uuid4())
    }
    
    broadcast_message = {
            "cmd": "message_new",
            "message": sendmessage,
            "channel": message.channel.name,
            "global": True
        }
    
    try:
        saved = channels.save_channel_message(message.channel.name, sendmessage)
        if not saved:
            Logger.error(f"Failed to save message in shared channel '{message.channel.name}'")
            return

        Logger.info(
            f"Message received in shared channel '{message.channel.name}': {message.content}"
        )
        print("Sending!")
        connected_clients = next(
            (obj.connected_clients for obj in gc.get_objects() if isinstance(obj, server.OriginChatsServer)),
            []
        )
        if not connected_clients:
            Logger.warning("No connected clients to broadcast to")
            return

        await broadcast_to_all(connected_clients, broadcast_message)

    except Exception as e:
        Logger.error(f"Discord bridge error in channel '{message.channel.name}': {e}")

async def start_bot():
    await bot.start(DISCORD_BOT_TOKEN)

async def on_new_message(ws, message_data, server_data=None):

    channel_name = message_data.get('channel')
    if not channel_name or channel_name not in sharedchannels:
        print ("Invalid Channel.")
        return

    guild = bot.get_guild(int(DISCORD_GUILD_ID))
    if not guild:
        return

    username = message_data.get('username', '')
    content = message_data.get('content', '')
    channel = get(guild.text_channels, name=channel_name)
    if channel:
        print ("Sending to channel!")
        await channel.send(username + ": " + content)
    else:
        print ("Channel not found!")
    


def init():
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(start_bot())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.create_task(start_bot())

init()
