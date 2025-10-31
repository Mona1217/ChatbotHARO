import sys
import os

# ensure project root is on sys.path so "core" package can be imported when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.chatbot import ChatBotCore

bot = ChatBotCore()
user = "test_user"

print("🧠 Simulación de conversación con el bot.\n")

while True:
    msg = input("Tú: ")
    if msg.lower() in ["salir", "exit", "quit"]:
        print("👋 Fin de la conversación.")
        break

    respuesta = bot.recibir_mensaje(user, msg)
    print(f"Bot: {respuesta}\n")
