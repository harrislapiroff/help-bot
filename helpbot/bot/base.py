from textwrap import dedent

import openai


__all__ = ['AbstractBot', 'OpenAIResponseBot']


class AbstractBot:
    def __init__(self, config: dict):
        self.config = config

    def get_response(message):
        raise NotImplementedError()

    def respond():
        raise NotImplementedError()
    
    def send_message():
        raise NotImplementedError()
    
    def on_message():
        raise NotImplementedError()
    
    def run():
        raise NotImplementedError()
    

class OpenAIResponseBot(AbstractBot):
    SYSTEM_PROMPT = dedent("""
        You are a friendly and helpful assistant who likes to answer questions.

        * Users will refer to you as HelpBot and you can refer to yourself by that name as well.
        * You can use emoji in your responses.
        * You can use markdown in your responses.
    """).strip()

    def __init__(self, config: dict):
        super().__init__(config)

        self.message_history = []

        assert 'openai_api_key' in self.config, 'API key not found in config'

        openai.api_key = self.config['openai_api_key']

    def on_message(self, message: str):
        self.message_history.append({'role': 'user', 'content': message})
        response = self.get_response(message)
        self.send_message(response)

    def send_message(self, message: str):
        self.message_history.append({'role': 'assistant', 'content': message})

    def get_message_history(self):
        return self.message_history
    
    def get_system_prompt(self):
        return self.SYSTEM_PROMPT

    def get_response(self, message: str):
        # Use the system prompt and the last 5 messages to generate a response
        messages = [{'role': 'system', 'content': self.get_system_prompt()}] + self.get_message_history()[-5:]
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=messages,
            temperature=0.9,
            max_tokens=150,
        )

        return response.choices[0]['message']['content']