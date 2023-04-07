from helpbot.bot.base import OpenAIResponseBot


__all__ = ['ShellBot']


class ShellBot(OpenAIResponseBot):
    def respond(self, message):
        print(message)

    def send_message(self, message: str):
        super().send_message(message)
        print(message)

    def run(self):
        while True:
            message = input(">>> ")
            self.on_message(message)