import discord
import openai
from typing import Iterable

from helpbot.bot.openai import OpenAIReactBot


__all__ = ['DiscordBot']


class DiscordBot(OpenAIReactBot):
    def __init__(self, config: dict):
        super().__init__(config)

        assert 'discord_token' in self.config, 'Token not found in config'

        if 'user_allowlist' not in self.config:
            self.config['user_allowlist'] = []

        self.client = discord.Client(intents=discord.Intents.default())

        # Register a message handler
        @self.client.event
        async def on_message(message) -> None:
            if not self._response_allowed(message):
                return
            response = await self.get_response(message)
            await self.send_message(response, self.get_context(message))

    def _response_allowed(self, message: discord.Message) -> bool:
        # If the message is from the bot itself, ignore
        if message.author == self.client.user:
            return False
        
        # If the message is from a user in the allowlist, allow
        if isinstance(message.channel, discord.channel.DMChannel) and str(message.author) in self.config['user_allowlist']:
            return True
        
        # If the message is in a channel and the bot is mentioned, allow
        if not isinstance(message.channel, discord.channel.DMChannel) and self.client.user.mentioned_in(message):
            return True
        
        # Otherwise, ignore
        return False
    
    async def get_message_history(self, context: dict) -> Iterable[dict]:
        "Instead of using the message history, we'll use the Discord API."
        channel = context['channel']
        messages = sorted([x async for x in channel.history(limit=5)], key=lambda m: m.created_at)
        # Let's only include recent messages from the user. The bot gets confused when it sees its own replies
        return [{
            'role': 'user',
            'content': m.content
        } for m in messages if m.author != self.client.user]
    
    def get_context(self, message):
        context = super().get_context(message)
        return {**context, 'channel': message.channel}


    async def on_message(self, message: discord.Message) -> None:
        async with message.channel.typing():
            response = await self.get_response(message.content)
            await self.send_message(response, self.get_context(message))

    async def send_message(self, message, context: dict) -> None:
        if message != '':
            await context['channel'].send(message)

    def run(self) -> None:
        self.client.run(self.config['discord_token'])