import logging
import os

from helpbot.bot import DiscordBot

def main():
    logging.basicConfig(level=logging.DEBUG)
    bot = DiscordBot({
        'openai_api_key': os.environ['OPENAI_API_KEY'],
        'openai_model': os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
        'discord_token': os.environ['DISCORD_BOT_TOKEN'],
        'user_allowlist': os.environ.get('DISCORD_DM_ALLOWLIST', '').split(','),
    })
    bot.run()