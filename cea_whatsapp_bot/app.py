# app.py"""""""""""""""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from twilio.twiml.messaging_response import MessagingResponse

from config import settings
from core.bot import ChatBotCore
from storage.db import init_db
import traceback

# --- Inicialización de base de datos (si aplica) ---
init_db()

# --- App & CORS ---
app = Flask(__name__, static_folder="static", static_url_path="/static")
# Habilita CORS solo para los endpoints de webhooks (útil en desarrollo)
CORS(app, resources={r"/webhook/*": {"origins": ["http://localhost:5000", "http://127.0.0.1:5000"]}})

# --- Bot Core ---
# Si tu ChatBotCore acepta un provider inyectable, puedes pasar un FakeProvider aquí.
bot = ChatBotCore()

@app.get("/diag/si")
def diag_si():
    return {
        "ok": True,
        "service": "whatsapp-bot",
        "status": "online"
    }, 200


# ---------- Utils ----------
def _actions_to_messages(result):
    """
    Transforma la salida del core a una lista de mensajes de texto simples.
    - Si result es str -> [{"from":"bot","text":str}]
    - Si result es lista de acciones -> filtra 'reply'/'send_message' con 'text'
    """
    if isinstance(result, str):
        return [{"from": "bot", "text": result}]

    messages = []
    if isinstance(result, list):
        for a in result:
            if not isinstance(a, dict):
                continue
            action = a.get("action")
            text = a.get("text")
            if action in ("reply", "send_message") and text:
                messages.append({"from": "bot", "text": text})
            # Si manejas plantillas, podrías renderizarlas aquí:
            # elif action == "send_template":
            #     name = a.get("name")
            #     params = a.get("params", {})
            #     messages.append({"from": "bot", "text": f"[plantilla:{name}] {params}"})
    return messages or [{"from": "bot", "text": "✅ Recibido."}]

# ---------- Rutas ----------
@app.get("/")
def home():
    """Ping/estado simple del servicio."""
    return f"{settings.PROJECT_NAME} activo 🚗"

@app.get("/health")
def health():
    """Healthcheck para monitoreo."""
    return jsonify({"ok": True, "service": settings.PROJECT_NAME, "version": getattr(settings, "VERSION", "dev")})

@app.get("/demo")
def demo_page():
    """
    Sirve el emulador web.
    Coloca tu index.html y assets (logoHARO.png, etc.) dentro de /static
    """
    return send_from_directory("static", "index.html")

@app.post("/webhook/incoming")
def webhook_incoming():
    """
    Webhook JSON para el emulador web (React/HTML).
    Espera algo como:
    {
      "conversation_id":"web-123",
      "from":"web-demo-usuario",
      "type":"text",
      "text":"menu",
      "message_id":"webmsg-xyz"
    }
    """
    payload = request.get_json(force=True, silent=True) or {}
    user_id = payload.get("from", "anonimo-web")
    mensaje = (payload.get("text") or "").strip()

    try:
        result = bot.handle_message(user_id, mensaje)
        messages = _actions_to_messages(result)
        return jsonify({"ok": True, "messages": messages})

    except Exception as e:
        traceback.print_exc()  # imprime la traza en la consola
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

@app.post("/chat")
def chat_http():
    """
    HTTP JSON simple para pruebas (Postman/curl).
    Body:
    { "user_id": "u1", "mensaje": "hola" }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id", "anonimo")
    mensaje = (data.get("mensaje") or "").strip()

    try:
        result = bot.handle_message(user_id, mensaje)
        # Para compatibilidad previa dejamos "respuesta" como texto concatenado
        messages = _actions_to_messages(result)
        texto = "\n".join([m.get("text", "") for m in messages]) if messages else ""
        return jsonify({"ok": True, "respuesta": texto, "messages": messages})
    except Exception as e:
        traceback.print_exc()  # imprime la traza en la consola
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

@app.post("/whatsapp")
def whatsapp_webhook():
    """
    Webhook de Twilio (WhatsApp). Recibe application/x-www-form-urlencoded.
    """
    from_number = request.form.get("From", "unknown")
    body = request.form.get("Body", "")

    try:
        respuesta = bot.handle_message(from_number, body)
        # A Twilio le devolvemos siempre texto plano (no JSON).
        if isinstance(respuesta, list):
            # Si son acciones, las convertimos a un único texto amigable.
            msgs = _actions_to_messages(respuesta)
            text = "\n".join([m.get("text", "") for m in msgs]) if msgs else "✅ Recibido."
        else:
            text = str(respuesta) if respuesta is not None else "✅ Recibido."

        twiml = MessagingResponse()
        twiml.message(text)
        return str(twiml)
    except Exception as e:
        twiml = MessagingResponse()
        twiml.message(f"Lo siento, ocurrió un error: {e}")
        return str(twiml)

# ---------- Errores comunes ----------
@app.errorhandler(404)
def not_found(_e):
    return jsonify({"ok": False, "error": "Ruta no encontrada"}), 404

@app.errorhandler(405)
def method_not_allowed(_e):
    return jsonify({"ok": False, "error": "Método no permitido"}), 405

# ---------- Main ----------
if __name__ == "__main__":
    # Asegúrate de que settings.PORT exista; si no, usa 5000 por defecto:
    port = getattr(settings, "PORT", 5000)
    app.run(host="0.0.0.0", port=port, debug=True)
