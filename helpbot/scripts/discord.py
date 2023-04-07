import os

from helpbot.bot import DiscordBot

def main():
    bot = DiscordBot({
        'openai_api_key': os.environ['OPENAI_API_KEY'],
        'discord_token': os.environ['DISCORD_BOT_TOKEN'],
        'user_allowlist': os.environ.get('DISCORD_USER_ALLOWLIST', '').split(','),
    })
    bot.run()