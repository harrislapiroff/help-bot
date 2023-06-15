import logging
import os
import asyncio

from helpbot.bot import ShellBot


def main():
    logging.basicConfig(level=logging.WARNING)
    bot = ShellBot({
        'openai_api_key': os.environ['OPENAI_API_KEY'],
        'openai_model': os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
    })
    loop = asyncio.get_event_loop()
    loop.run_until_complete(bot.run())
