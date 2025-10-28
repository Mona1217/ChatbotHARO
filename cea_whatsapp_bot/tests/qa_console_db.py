# tests/qa_console_db.py
from core.bot import ChatBotCore

def main():
    bot = ChatBotCore()
    user_id = "qa"
    # IP/UA simulados para consentimiento
    st = bot.sessions.get(user_id)
    st["_ip"] = "127.0.0.1"
    st["_ua"] = "QA-Console/1.0"

    print("QA Chatbot (DB mode). Escribe 'exit' para salir.")
    print(bot.handle_message(user_id, "inicio"))
    while True:
        msg = input(">> ").strip()
        if msg.lower() in {"exit", "salir", "quit"}:
            break
        resp = bot.handle_message(user_id, msg)
        print(resp)

if __name__ == "__main__":
    main()
