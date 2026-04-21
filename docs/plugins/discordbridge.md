# Discord Bridge Plugin
> How to setup the plugin
---
To setup the plugin, first, in the plugin folder, create a file called discordbridge.env. In this file, add **two** lines.
```
DISCORD_BOT_TOKEN = 
DISCORD_GUILD_ID = 
```
Next, create a Discord bot with the message intents, and whatever other perms you want to give it. I chose admin because I'm that cool and trust myself, but realistically it just needs message reading, sending, and editing. Make sure you also enable the "Message Content" intent. After creation grab your bot token, paste it in the .env, and the guild id also in the .env. In the end it should look something like:
```
DISCORD_BOT_TOKEN = MTAyMzQ1Njc4OTAxMjM0NTY3OA.GBgHhJ.FakeTokenExample1234567890abcdef
DISCORD_GUILD_ID = 12438329893
```
Next, simply make sure everything is in the plugins folder, and run it!
> [!NOTE]
> Any correlation to real tokens or guild IDS is coincidental.