import requests


class TelegramBot:

    def send_text(bot_message):
        """
        Usage:\n
        >>from telegram_bot import TelegramBot \n
        >>TelegramBot.send_text("message") \n
        """
        bot_token = "2016290647:AAFnSNJFb9ilc3-9n6Am1SjrHrXULEH10xs"
        bot_chatID = "-647701188"
        send_text = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={bot_chatID}&parse_mode=Markdown&text={bot_message}"

        bot_response = requests.get(send_text)
        return bot_response.json()


"""
Creating a new bot:
1. On Telegram, search @ BotFather, send him a “/start” message.
2. Send another “/newbot” message, then follow the instructions to setup a name and a username.
3. Your bot is now ready. Be sure to save a backup of your API token, and correct, this API token is your bot_token.
4. On Telegram, create a new chat, then search your bot (by the username you just created) and send a “/start @{bot_name}” message.
5. Open a new tab with your browser, enter https://api.telegram.org/bot<yourtoken>/getUpdates , replace <yourtoken> with your API token, press enter and you should see something like this:
{"ok":true,"result":[{"update_id":77xxxxxxx,"message":{"message_id":550,"from":{"id":34xxxxxxx,"is_bot":false,"first_name":"Man Hay","last_name":"Hong","username":"manhay212","language_code":"en-HK"}
Look for “id”, for instance, 34xxxxxxx above is my chat id.
"""
