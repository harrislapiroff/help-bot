import os

from helpbot.bot import ShellBot


def main():
    bot = ShellBot({
        'openai_api_key': os.environ['OPENAI_API_KEY'],
    })
    bot.run()