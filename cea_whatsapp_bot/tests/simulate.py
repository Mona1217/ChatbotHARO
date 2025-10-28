from core.bot import ChatBotCore
bot = ChatBotCore()
uid = "tester"
print(bot.handle_message(uid, "inicio"))
print("---")
print(bot.handle_message(uid, "1"))
print("---")
print(bot.handle_message(uid, "b"))
print("---")
print(bot.handle_message(uid, "cotizar"))
print("---")
print(bot.handle_message(uid, "¿qué necesito para c1?"))
