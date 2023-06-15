import datetime
import logging
import random
import json
from textwrap import dedent

import openai
import wikipedia
import numexpr

from helpbot.bot.base import AbstractBot
from helpbot.utils import json_single_line

from typing import Any, Optional, Iterable, Tuple

logging.basicConfig(level=logging.INFO)


def wikipedia_(
    search : Optional[str] = None,
    exact_title : Optional[str] = None
) -> str:
    if all([search, exact_title]):
        raise ValueError('Only one of search or exact_title can be specified')

    if not any([search, exact_title]):
        raise ValueError('One of search or exact_title must be specified')

    if search:
        return ', '.join(wikipedia.search(search))

    return wikipedia.page(exact_title, auto_suggest=False).summary


def calculate(expression : str):
    """Calculate a mathematical expression"""
    return numexpr.evaluate(expression).item()


def random_(choices : Optional[Iterable] = None, range : Optional[Tuple[int]] = None):
    """Generate a random number or make a random choice."""
    if all([choices, range]):
        raise ValueError('Only one of choices or range can be specified')
    
    if not any([choices, range]):
        raise ValueError('One of choices or range must be specified')
    
    if choices:
        return random.choice(choices)
    
    return random.randint(*range)


class OpenAIReactBot(AbstractBot):
    SYSTEM_PROMPT = dedent("""
        You are a friendly and helpful assistant who likes to answer questions.
        Use as many function calls as you need to reach an answer.
        When you have a final response to a user's query use the conclude function to respond and end the conversation.
    """).strip()

    MAX_TRIES = 10

    FUNCTIONS = [
        {
            'name': 'wikipedia',
            'description': (
                'Query Wikipedia for a search term or exact title. If you include a search term, '
                'the response will be a list of possible titles. If you include an exact title, '
                'the response will be the summary of the page. Only use one or the other. After '
                'running a search to get a list of pages, *do* run the function again with an '
                'exact title to get a summary. A list of page titles is not sufficient to deduce '
                'an answer.'
            ),
            'parameters': {
                'type': 'object',
                'properties': {
                    'search': {
                        'type': 'string',
                        'description': 'Keywords to search for',
                    },
                    'exact_title': {
                        'type': 'string',
                        'description': 'The page title to search for. Must be exact',
                    }
                },
            }
        },
        {
            'name': 'calculate',
            'description': 'Calculate a mathematical expression',
            'parameters': {
                'type': 'object',
                'properties': {
                    'expression': {
                        'type': 'string',
                        'description': 'The expression to calculate',
                    },
                },
                'required': ['expression'],
            },
        },
        {
            'name': 'random',
            'description': 'Generate a random number or make a random choice.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'choices': {
                        'type': 'array',
                        'description': 'A list of choices to pick from',
                        'items': {
                            'type': 'string',
                        },
                    },
                    'range': {
                        'type': 'array',
                        'description': 'A range of numbers to pick from',
                        'items': {
                            'type': 'number',
                        },
                        'minItems': 2,
                        'maxItems': 2,
                    },
                },
            },
        },
        {
            'name': 'conclude',
            'description': 'Express a final response to the user. This will end your train of thought and you will not be able to take other actions.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'answer': {
                        'type': 'string',
                        'description': 'The response to convey to the user',
                    },
                    'emoji': {
                        'type': 'string',
                        'enum': ['💡', '🤔', '😕', '🤓', '😎', '❤️', '✅', '🙅🏻‍♀️', '🎲', '🪙'],
                        'description': 'An emoji to include with the response. The default 💡 is good for most cases, but you may optionally change it according to the mood of your reply.',
                    }
                },
                'required': ['answer'],
            }
        },
    ]

    ACTIONS = {
        'wikipedia': wikipedia_,
        'calculate': calculate,
        'random': random_,
    }

    def __init__(self, config: dict):
        super().__init__(config)

        self.message_history = []

        assert 'openai_api_key' in self.config, 'API key not found in config'

        openai.api_key = self.config['openai_api_key']
        self.model = self.config.get('openai_model', 'gpt-3.5-turbo')

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

    def get_system_prompt(self, context: dict = {}):
        return self.SYSTEM_PROMPT + (
            '\n\n'
            f'Today\'s date is: {datetime.date.today()}\n'
            f'You are powered by the OpenAI {self.model} model\n'
        )
    

    def get_context(self, extra_context: Any):
        """
        We don't need this method here, but subclasses may want to override it to provide
        additional context to methods like get_message_history and get_system_prompt
        """
        return {}

    async def get_response(self, message: str, extra_context : Optional[Any] = {}) -> str:
        messages = [
            {'role': 'system', 'content': self.get_system_prompt(extra_context)},
            {'role': 'user', 'content': message},
        ]

        i = 0
        while i < self.MAX_TRIES:
            i += 1

            logging.info(f'Generating response with message history: {messages}')

            try:
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    functions=self.FUNCTIONS,
                    function_call='auto',
                    temperature=0.25,
                    stop=['PAUSE']
                )
            except openai.error.RateLimitError as e:
                await self.send_message('Sorry, I couldn\'t reach my brain. Try again in a moment?', self.get_context(extra_context))
                break
            except Exception as e:
                await self.send_message(f'🚨 {type(e).__name__}: {e}', self.get_context(extra_context))
                break


            if response_text := response.choices[0]['message']['content']:
                messages.append({'role': 'assistant', 'content': response_text})
                await self.send_message(f'💬 {response_text}', self.get_context(extra_context))
                break

            elif fn := response.choices[0]['message']['function_call']:

                try:
                    args = json.loads(fn.arguments)
                except json.decoder.JSONDecodeError:
                    messages.append({'role': 'assistant', 'function_call': fn, 'content': None})
                    messages.append({'role': 'function', 'name': fn.name, 'content': '{"error": "Invalid JSON"}'})
                    await self.send_message(f'🚨 Bot provided invalid JSON for function {fn.name}: {fn.arguments}', self.get_context(extra_context))

                if fn.name == 'conclude':
                    answer = args['answer']
                    messages.append({'role': 'assistant', 'function_call': fn, 'content': None})
                    await self.send_message(f'{args.get("emoji", "💡")} {answer}', self.get_context(extra_context))
                    break

                try:
                    messages.append({'role': 'assistant', 'function_call': fn, 'content': None})
                    logging.info(f'Calling function: {fn.name} with arguments: {fn.arguments}')
                    args_for_log = json_single_line(args)
                    await self.send_message(f'🤖 Running **{fn.name}** with `{args_for_log}`...', self.get_context(extra_context))
                    result = self.ACTIONS[fn.name](**args)
                    await self.send_message('🤖 Done ✅', self.get_context(extra_context))
                    messages.append({'role': 'function', 'name': fn.name, 'content': json.dumps(result)})

                except Exception as e:
                    messages.append({'role': 'function', 'name': fn.name, 'content': json.dumps(f'{type(e)}: {e}')})
                    await self.send_message(f'🚨 {type(e).__name__}: {e}', self.get_context(extra_context))
        else:
            await self.send_message(f'🥺: I couldn\'t find a response to that after {self.MAX_TRIES} actions, sorry.', self.get_context(extra_context))