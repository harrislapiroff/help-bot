import datetime
import logging
import re
from textwrap import dedent

import openai
import wikipedia

from helpbot.bot.base import AbstractBot
from helpbot.utils import count_message_tokens

class OpenAIReactBot(AbstractBot):
    SYSTEM_PROMPT = dedent("""
        You are a friendly and helpful assistant who likes to answer questions.

        You exist in a loop of Thought, Action, PAUSE, and Result.
        At the end of the loop you output an Answer
        Use Thought to describe your thoughts about the question you have been asked.
        Use Action to run one of the actions available to you - then return PAUSE.
        Result will be the result of running those actions.
        Use Answer to describe your answer to the question. Ensure that your answer does respond to the user's original question!

        You can use the following actions and only the these actions:

        wikipedia_list:
        e.g., wikipedia_list: U.S. Presidents
        Returns a list of Wikipedia pages matching a search term.

        wikipedia:
        e.g., wikipedia: List of presidents of the United States
        Returns the summary of a Wikipedia page. The title must be exact, so it is best to run wikipedia_list first to get the title of an article you want.

        Attempts to use other actions will not work.

        Example session:

        User: How do the populations of Boston and San Francisco compare?
        Thought: I should look up Wikipedia pages for the populations of Boston and San Francisco.
        Action: wikipedia_list: Boston
        Result: Boston, Boston Marathon bombing, Boston Red Sox
        Action: wikipedia: Boston
        Result: [content of Boston Wikipedia page]
        Thought: The population of Boston is 692,600. I should look up the population of San Francisco.
        Action: wikipedia_list: San Francisco
        Result: San Francisco, San Francisco 49ers, San Francisco Giants
        Action: wikipedia: San Francisco
        Result: [content of San Francisco Wikipedia page]
        Thought: The population of San Francisco is 883,305. I should compare the populations of Boston and San Francisco.
        Answer: The population of Boston is 692,600 and the population of San Francisco is 883,305. Boston has 190,705 fewer people than San Francisco.
    """).strip()

    MODEL = 'gpt-3.5-turbo'
    MAX_TRIES = 5
    ACTIONS_RE = re.compile('^Action: (\w+): (.*)$')
    ACTIONS = {
        'wikipedia_list': lambda search: ', '.join(wikipedia.search(search)),
        'wikipedia': lambda page: wikipedia.page(page, auto_suggest=False).summary,
    }

    def __init__(self, config: dict):
        super().__init__(config)

        self.message_history = []

        assert 'openai_api_key' in self.config, 'API key not found in config'

        openai.api_key = self.config['openai_api_key']

    async def on_message(self, message: str):
        # For clarity, let's clear the message history when we receive a new query
        self.message_history = [{'role': 'user', 'content': message}]
        try:
            response = await self.get_response(message)
        except Exception as e:
            response = f'An error occurred: {e}'
        await self.send_message(response)

    async def send_message(self, message: str, context: dict = {}):
        self.message_history.append({'role': 'assistant', 'content': message})

    async def get_message_history(self, context: dict = {}):
        return self.message_history[-5:]

    def get_system_prompt(self, context: dict = {}):
        return self.SYSTEM_PROMPT + f'\n\n Today\'s date is: {datetime.date.today()}'

    def get_context(self, message):
        """
        We don't need this method here, but subclasses may want to override it to provide
        additional context to methods like get_message_history and get_system_prompt
        """
        return {}

    async def get_response(self, message: str) -> str:
        # Use the system prompt and the last 5 messages to generate a response
        messages = [{'role': 'system', 'content': self.get_system_prompt()}] + await self.get_message_history(self.get_context(message))

        # We also send messages to keep the user updated on what the bot is doing
        i = 0
        while i < self.MAX_TRIES:
            i += 1
            message_tokens = count_message_tokens(messages, self.MODEL)
            response = openai.ChatCompletion.create(
                model=self.MODEL,
                messages=messages,
                temperature=0.25,
                max_tokens=4096 - message_tokens - 10,  # 10 is a buffer to account for any token counting inaccuracy
                stop=['PAUSE']
            )
            response_text = response.choices[0]['message']['content']

            # After the first response we maintain a message history just for this query
            messages = [
                {'role': 'system', 'content': self.get_system_prompt(self.get_context(message))},
                {'role': 'user', 'content': f'Question: {message}'},
                {'role': 'assistant', 'content': response_text},
            ]

            for line in response_text.strip().split('\n'):
                logging.info(f'Line: {line}')
                if line.startswith('Thought: '):
                    await self.send_message(line.replace('Thought: ', '💭 '), self.get_context(message))

                elif line.startswith('Action: '):
                    try:
                        action = self.ACTIONS_RE.match(line)
                        action_type, action_args = action.groups()
                        if action_type in self.ACTIONS:
                            # Update the user on what the bot is doing
                            await self.send_message(f'🤖 {action_type}: {action_args}', self.get_context(message))
                            action_result = self.ACTIONS[action_type](action_args)
                            await self.send_message(f'📥 Result received', self.get_context(message))
                            messages.append({'role': 'assistant', 'content': f'Result: {action_result}'})
                    # This should happen when an action is not in the ACTIONS dict
                    except AttributeError:
                        await self.send_message(f'🚨 Invalid action: {line}', self.get_context(message))
                        messages.append({'role': 'assistant', 'content': f'Result: That action isn\'t allowed. I should try one of these: {", ".join(self.ACTIONS.keys())}'})
                    # This should happen when a wikipedia lookup fails
                    except wikipedia.PageError:
                        await self.send_message(f'🚨 Wikipedia page not found: {action.groups()[1]}', self.get_context(message))
                        messages.append({'role': 'assistant', 'content': f'Result: That wikiepedia page wasn\'t found. I should try a different one or use the wikipedia_list action.'})
                    # Catch all for any other exceptions
                    except Exception as e:
                        await self.send_message(f'🚨 {type(e).__name__} running {action.groups()[0]}: {e}', self.get_context(message))
                        messages.append({'role': 'assistant', 'content': f'Result: That action failed. I should try another one.'})

                # The bot is not supposed to send a Result line, so we ignore it
                elif line.startswith('Result: '):
                    pass

                # If it's anything else, go ahead and send it as the final answer
                elif line != '':
                    return line.replace('Answer: ', '💡 ')