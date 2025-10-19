# app.py
# -*- coding: utf-8 -*-
import os
from pathlib import Path

# ========= CARGA ROBUSTA DE .env =========
from dotenv import load_dotenv, find_dotenv

# 1) Busca .env desde el CWD; si no, usa junto a app.py
DOTENV_PATH = find_dotenv(usecwd=True)
if not DOTENV_PATH:
    DOTENV_PATH = str(Path(__file__).with_name(".env"))

# 2) Carga con override=True para asegurar visibilidad
if DOTENV_PATH and os.path.exists(DOTENV_PATH):
    load_dotenv(DOTENV_PATH, override=True)
    print(f"[.env] Cargado desde: {DOTENV_PATH}")
else:
    print("[.env] NO encontrado. Colócalo junto a app.py o ejecútalo desde esa carpeta.")

# ========= IMPORTS WEB =========
from flask import Flask, request, abort
from twilio.twiml.messaging_response import MessagingResponse
from collections import defaultdict

# Estructura supuesta:
# core/
#   menuHandler.py  -> class MenuHandler
#   twilioUtils.py  -> send_whatsapp (Twilio Client lazy)
from core.menuHandler import MenuHandler
from core.twilioUtils import send_whatsapp

# (Opcional) pyngrok para túnel (solo si USE_NGROK=true)
try:
    from pyngrok import ngrok, conf
    _HAS_PYNGROK = True
except Exception:
    _HAS_PYNGROK = False

# ========= APP =========
app = Flask(__name__)

# Estado en memoria (prod: Redis/BD)
handlers = {}
user_state = defaultdict(lambda: "inicio")

def send_otp_through_twilio(to_number: str, body: str) -> None:
    """Adapter para que MenuHandler envíe OTP por WhatsApp (Twilio)."""
    send_whatsapp(to_number, body)

def get_handler(user_id: str) -> MenuHandler:
    if user_id not in handlers:
        handlers[user_id] = MenuHandler(send_otp_callback=send_otp_through_twilio)
    return handlers[user_id]

# ========= RUTAS =========
@app.post("/whatsapp")
def whatsapp_webhook():
    """Endpoint que Twilio llama en cada mensaje entrante de WhatsApp."""
    from_number = request.form.get("From")      # ej: 'whatsapp:+57XXXXXXXXXX'
    body = (request.form.get("Body") or "").strip()

    if not from_number:
        abort(400, "Missing 'From'")

    estado_actual = user_state[from_number]
    handler = get_handler(from_number)
    handler.set_user(from_number)  # guarda el número para OTP

    respuesta, nuevo_estado = handler.procesar_opcion(estado_actual, body)
    user_state[from_number] = nuevo_estado

    twiml = MessagingResponse()
    twiml.message(respuesta)
    return str(twiml)

@app.get("/health")
def health():
    return "ok", 200

# ========= NGROK OPCIONAL =========
def maybe_start_ngrok(port: int):
    """
    Levanta ngrok si USE_NGROK=true y pyngrok está instalado.
    Variables soportadas (en .env o entorno):
      - USE_NGROK=true|1|yes|on
      - NGROK_AUTHTOKEN=...
      - NGROK_REGION=us|sa|eu|ap|au|jp|in
      - NGROK_DEBUG=true (opcional: logs verbosos)
    """
    use_ngrok = (os.environ.get("USE_NGROK", "") or "").lower() in {"1", "true", "yes", "on"}

    # Debug del entorno
    print("DEBUG USE_NGROK:", os.environ.get("USE_NGROK"))
    print("DEBUG NGROK_REGION:", os.environ.get("NGROK_REGION"))
    print("DEBUG NGROK_AUTHTOKEN set?:", bool(os.environ.get("NGROK_AUTHTOKEN")))

    if not use_ngrok:
        print("INFO: USE_NGROK no está activo. Omitiendo túnel.")
        return None

    if not _HAS_PYNGROK:
        print("ERROR: pyngrok no está instalado. Ejecuta: pip install pyngrok")
        return None

    # Config mínima de ngrok: token y región (LEÍDAS POR NOMBRE DE VARIABLE)
    authtoken = os.environ.get("33CzmNhvfNe8OsLr3grhp2aB2WT_vbKKqnDJXVuPmiQSHyGF")
    region = os.environ.get("sa")
    if authtoken:
        conf.get_default().auth_token = authtoken
    if region:
        conf.get_default().region = region

    # Logs de ngrok (opcional)
    if (os.environ.get("NGROK_DEBUG", "") or "").lower() in {"1", "true", "yes", "on"}:
        conf.get_default().log = "stdout"
        conf.get_default().log_level = "debug"

    # Cierra túneles previos (por si relanzas)
    try:
        for t in ngrok.get_tunnels():
            try:
                ngrok.disconnect(t.public_url)
            except Exception:
                pass
    except Exception:
        pass

    # Abre el túnel
    tunnel = ngrok.connect(addr=port, proto="http", bind_tls=True)
    public_url = tunnel.public_url  # p.ej. https://xxxxx.ngrok-free.app

    print("\n" + "=" * 84)
    print(" 🌐 NGROK TÚNEL ACTIVO")
    print(f"    Público: {public_url}")
    print(" 📌 Pega en Twilio → WhatsApp Sandbox → WHEN A MESSAGE COMES IN:")
    print(f"    {public_url}/whatsapp")
    print(" 🧪 Dashboard local ngrok: http://127.0.0.1:4040")
    print("=" * 84 + "\n")

    return public_url

# ========= MAIN =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))

    # *** SIN RELOADER para evitar túneles duplicados ***
    maybe_start_ngrok(port)
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
