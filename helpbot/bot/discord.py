import discord
import openai
from typing import Iterable

from helpbot.bot.base import OpenAIResponseBot


__all__ = ['DiscordBot']


class DiscordBot(OpenAIResponseBot):
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
            await self.send_message(response, message.channel)

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
    
    async def get_message_history(self, channel: discord.TextChannel) -> Iterable[dict]:
        "Instead of using the message history, we'll use the Discord API."
        messages = sorted([x async for x in channel.history(limit=5)], key=lambda m: m.created_at)
        return [{
            'role': 'user' if m.author != self.client.user else 'assistant',
            'content': m.content
        } for m in messages]

    async def get_response(self, message: str) -> str:
        # Use the system prompt and the last 5 messages to generate a response
        messages = [{'role': 'system', 'content': self.get_system_prompt()}] + await self.get_message_history(message.channel)
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=messages,
            temperature=0.9,
            max_tokens=150,
        )
        return response.choices[0]['message']['content']


    async def on_message(self, message: discord.Message) -> None:
        async with message.channel.typing():
            response = self.get_response(message.content)
            self.send_message(response, message.channel)

    async def send_message(self, message, channel) -> None:
        await channel.send(message)

    def run(self) -> None:
        self.client.run(self.config['discord_token'])