# app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from twilio.twiml.messaging_response import MessagingResponse

from config import settings
from core.bot import ChatBotCore
from services.si_client import SIClient  # <-- importa el cliente para el pre-flight
import traceback
import sys

# --- App & CORS ---
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(
    app,
    resources={
        r"/webhook/*": {"origins": ["http://localhost:5000", "http://127.0.0.1:5000"]},
        r"/chat": {"origins": ["http://localhost:5000", "http://127.0.0.1:5000"]},
    },
)

# --- Bot Core ---
bot = ChatBotCore()

# ---------- Utils ----------
def _actions_to_messages(result):
    """
    Transforma la salida del core a una lista de mensajes de texto.
    - str -> [{"from":"bot","text": str}]
    - lista de acciones -> filtra 'reply'/'send_message' con 'text'
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
            # Plantillas (opcional)
            # elif action == "send_template":
            #     messages.append({"from": "bot", "text": f"[plantilla:{a.get('name')}] {a.get('params',{})}"})
    return messages or [{"from": "bot", "text": "✅ Recibido."}]

# ---------- Rutas ----------
@app.get("/")
def home():
    return f"{getattr(settings, 'PROJECT_NAME', 'Chatbot')} activo 🚗"

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "service": getattr(settings, "PROJECT_NAME", "bot"),
        "version": getattr(settings, "VERSION", "dev"),
    })

@app.get("/diag/si")
def diag_si():
    """
    Diagnostico en caliente de conectividad/autenticacion al SI.
    """
    si = SIClient(
        base_url=getattr(settings, "SI_BASE_URL", None),
        user=getattr(settings, "SI_USER", None),
        pwd=getattr(settings, "SI_PASS", None),
        bearer_token=getattr(settings, "SI_BEARER_TOKEN", None),
    )
    ok, detail = si.check_connectivity()
    return jsonify({
        "ok": ok,
        "detail": detail,
        "base": getattr(settings, "SI_BASE_URL", None)
    }), (200 if ok else 503)

@app.get("/demo")
def demo_page():
    # Sirve el emulador web (coloca index.html y assets en /static)
    return send_from_directory("static", "index.html")

@app.post("/webhook/incoming")
def webhook_incoming():
    """
    Webhook JSON para el emulador web.
    Body ejemplo:
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
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

@app.post("/chat")
def chat_http():
    """
    HTTP JSON simple para pruebas:
    { "user_id": "u1", "mensaje": "hola" }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id", "anonimo")
    mensaje = (data.get("mensaje") or "").strip()
    try:
        result = bot.handle_message(user_id, mensaje)
        messages = _actions_to_messages(result)
        texto = "\n".join([m.get("text", "") for m in messages]) if messages else ""
        return jsonify({"ok": True, "respuesta": texto, "messages": messages})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500

@app.post("/whatsapp")
def whatsapp_webhook():
    """
    Webhook Twilio (WhatsApp). Recibe application/x-www-form-urlencoded.
    """
    from_number = request.form.get("From", "unknown")
    body = request.form.get("Body", "")
    try:
        respuesta = bot.handle_message(from_number, body)
        if isinstance(respuesta, list):
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

# ---------- Pre-flight SI ----------
def preflight_si_or_exit():
    """
    Verifica conectividad y autenticacion al SI antes de levantar el bot.
    Sale con codigo 1 si falla, para no dejar el bot 'ciego'.
    """
    si = SIClient(
        base_url=getattr(settings, "SI_BASE_URL", None),
        user=getattr(settings, "SI_USER", None),
        pwd=getattr(settings, "SI_PASS", None),
        bearer_token=getattr(settings, "SI_BEARER_TOKEN", None),
    )
    ok, detail = si.check_connectivity()
    if ok:
        print(f"[PRE-FLIGHT] Conectividad SI OK -> {detail}")
    else:
        print(f"[PRE-FLIGHT] FALLO conectividad/autenticacion SI -> {detail}")
        sys.exit(1)

# ---------- Main ----------
if __name__ == "__main__":
    # Verificar SI antes de iniciar Flask
    preflight_si_or_exit()

    port = getattr(settings, "PORT", 5000)  # <-- este es el puerto del BOT (Flask)
    app.run(host="0.0.0.0", port=port, debug=True)
