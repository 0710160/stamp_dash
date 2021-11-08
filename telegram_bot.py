import requests
from dotenv import load_dotenv
import os

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

class TelegramBot:

    def send_text(bot_message):
        """
        Usage:\n
        >>from telegram_bot import TelegramBot \n
        >>TelegramBot.send_text("message") \n
        """
        bot_token = BOT_TOKEN
        bot_chatID = "-647701188"
        send_text = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&parse_mode=Markdown&text={bot_message}"

        bot_response = requests.get(send_text)
        return bot_response.json()