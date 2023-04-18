from typing import Optional


__all__ = ['AbstractBot', ]


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
