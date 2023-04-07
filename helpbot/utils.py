import tiktoken

from typing import Iterable

def count_message_tokens(messages: Iterable[dict], model) -> int:
    encoding = tiktoken.encoding_for_model(model)
    # See this link for info on how messages are converted to tokens
    # https://github.com/openai/openai-python/blob/main/chatml.md
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens