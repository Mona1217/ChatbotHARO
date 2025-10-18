from flask import Flask, request, jsonify
from core.chatbot import ChatBotCore

app = Flask(__name__)
bot = ChatBotCore()

@app.route("/")
def home():
    return "Chatbot de Academia de Conducción 🚗 activo."

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_id = data.get("user_id", "anonimo")
    mensaje = data.get("mensaje", "")
    respuesta = bot.recibir_mensaje(user_id, mensaje)
    return jsonify({"respuesta": respuesta})

if __name__ == "__main__":
    app.run(debug=True)
