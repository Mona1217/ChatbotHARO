# app.py
from collections import deque
from datetime import datetime
import json
import os
import re
import logging
import sqlite3
from dataclasses import dataclass, field
from threading import Condition, Lock
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

load_dotenv()
app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/static",
)

# ========= Logging =========
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = app.logger  # usa el logger de Flask

# ========= Config =========
REQUIRED_ENV_VARS = (
    "WHATSAPP_VERIFY_TOKEN",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
)

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v24.0")
API_UNAVAILABLE_MESSAGE = os.getenv(
    "API_UNAVAILABLE_MESSAGE",
    "En este momento no estoy disponible, intenta mas tarde.",
)
BOT_PAUSED_MESSAGE = os.getenv(
    "BOT_PAUSED_MESSAGE",
    "En este momento no estoy disponible, intenta mas tarde.",
)
BOT_PAUSED = os.getenv("BOT_PAUSED", "false").strip().lower() in {"1", "true", "yes", "y"}
MONITOR_TOKEN = os.getenv("MONITOR_TOKEN", "").strip()
MONITOR_REFRESH_SECONDS = 5
MONITOR_DB_PATH = os.getenv("MONITOR_DB_PATH", "monitor_events.db").strip() or "monitor_events.db"
MONITOR_CORS_ORIGINS = {
    origin.strip()
    for origin in os.getenv(
        "MONITOR_CORS_ORIGINS",
        "http://127.0.0.1:8080,http://localhost:8080",
    ).split(",")
    if origin.strip()
}
MONITOR_CORS_PATHS = {
    "/monitor/events",
    "/api/monitor/events",
    "/monitor/pause",
    "/api/monitor/pause",
    "/monitor/stream",
    "/api/monitor/stream",
}

try:
    # 0 o negativo => historial sin limite en memoria.
    MONITOR_LOG_MAX = int(os.getenv("MONITOR_LOG_MAX", "0"))
except ValueError:
    MONITOR_LOG_MAX = 0

USE_WELCOME_TEMPLATE = os.getenv("USE_WELCOME_TEMPLATE", "false").strip().lower() in {"1", "true", "yes", "y"}
WELCOME_TEMPLATE_NAME = os.getenv("WELCOME_TEMPLATE_NAME", "welcome_haro")
WELCOME_TEMPLATE_LANG = os.getenv("WELCOME_TEMPLATE_LANG", "es_CO")

# ✅ Spring (tu backend real)
SPRING_BASE_URL = os.getenv("SPRING_BASE_URL", "http://localhost:8083").rstrip("/")

# ✅ Deduplicación para evitar reintentos duplicados
PROCESSED_MSG_IDS: set[str] = set()
MAX_PROCESSED_CACHE = 5000


# ========= Session State (solo si usas lógica local; puedes quitarlo si TODO vive en Spring) =========
@dataclass
class SessionState:
    step: str = "welcome"
    data: Dict[str, str] = field(default_factory=dict)


SESSIONS: Dict[str, SessionState] = {}
MESSAGE_EVENTS = deque(maxlen=MONITOR_LOG_MAX if MONITOR_LOG_MAX > 0 else None)
MESSAGE_EVENTS_LOCK = Lock()
MONITOR_DB_LOCK = Lock()
MONITOR_VERSION = 0
MONITOR_VERSION_COND = Condition()


# ========= Helpers =========
def validate_env() -> Tuple[bool, List[str]]:
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    return (len(missing) == 0, missing)


def normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def is_restart_command(text: str) -> bool:
    return normalize_text(text) in {"menu", "inicio", "reiniciar", "start"}


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", (email or "").strip()))


def parse_service_option(text: str) -> Optional[str]:
    value = normalize_text(text)
    mapping = {
        "1": "Ventas",
        "2": "Soporte tecnico",
        "3": "Agendar llamada",
        "ventas": "Ventas",
        "soporte": "Soporte tecnico",
        "soporte tecnico": "Soporte tecnico",
        "agendar": "Agendar llamada",
        "llamada": "Agendar llamada",
    }
    return mapping.get(value)


def normalize_event_text(value: Optional[str]) -> str:
    return (value or "").strip()


def get_monitor_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(MONITOR_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_monitor_db() -> None:
    with MONITOR_DB_LOCK:
        with get_monitor_db_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS monitor_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version INTEGER NOT NULL UNIQUE,
                    ts TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    peer TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_monitor_events_version ON monitor_events(version)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_monitor_events_peer_version ON monitor_events(peer, version)"
            )


def get_max_monitor_version_from_db() -> int:
    with MONITOR_DB_LOCK:
        with get_monitor_db_connection() as conn:
            row = conn.execute("SELECT COALESCE(MAX(version), 0) AS max_version FROM monitor_events").fetchone()
    return int(row["max_version"]) if row else 0


def insert_monitor_event_db(event: dict) -> None:
    with MONITOR_DB_LOCK:
        with get_monitor_db_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO monitor_events
                (version, ts, direction, event_type, peer, body, status, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(event.get("version", 0)),
                    event.get("ts", ""),
                    event.get("direction", ""),
                    event.get("event_type", ""),
                    event.get("peer", ""),
                    event.get("body", ""),
                    event.get("status", ""),
                    event.get("detail", ""),
                ),
            )


def add_monitor_event(
    direction: str,
    event_type: str,
    peer: str = "",
    body: Optional[str] = None,
    status: str = "ok",
    detail: str = "",
) -> None:
    global MONITOR_VERSION

    with MONITOR_VERSION_COND:
        MONITOR_VERSION += 1
        version = MONITOR_VERSION

    event = {
        "version": version,
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "direction": direction,
        "event_type": event_type,
        "peer": peer or "-",
        "body": normalize_event_text(body),
        "status": status,
        "detail": normalize_event_text(detail),
    }
    with MESSAGE_EVENTS_LOCK:
        MESSAGE_EVENTS.append(event)
    try:
        insert_monitor_event_db(event)
    except Exception as e:
        logger.exception("Error guardando evento en DB: %s", e)
    with MONITOR_VERSION_COND:
        MONITOR_VERSION_COND.notify_all()


def get_monitor_events(since: int = 0, peer: Optional[str] = None) -> List[dict]:
    where_clauses = []
    params: List[object] = []

    if since > 0:
        where_clauses.append("version > ?")
        params.append(since)

    if peer:
        where_clauses.append("peer = ?")
        params.append(peer)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = f"""
        SELECT version, ts, direction, event_type, peer, body, status, detail
        FROM monitor_events
        {where_sql}
        ORDER BY version ASC
    """

    try:
        with MONITOR_DB_LOCK:
            with get_monitor_db_connection() as conn:
                rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.exception("Error leyendo eventos de DB: %s", e)
        with MESSAGE_EVENTS_LOCK:
            events = list(MESSAGE_EVENTS)
        if peer:
            events = [ev for ev in events if ev.get("peer") == peer]
        if since > 0:
            events = [ev for ev in events if int(ev.get("version", 0)) > since]
        return events


def get_monitor_total_events(peer: Optional[str] = None) -> int:
    try:
        with MONITOR_DB_LOCK:
            with get_monitor_db_connection() as conn:
                if peer:
                    row = conn.execute(
                        "SELECT COUNT(*) AS total FROM monitor_events WHERE peer = ?",
                        (peer,),
                    ).fetchone()
                else:
                    row = conn.execute("SELECT COUNT(*) AS total FROM monitor_events").fetchone()
        return int(row["total"]) if row else 0
    except Exception as e:
        logger.exception("Error contando eventos de DB: %s", e)
        with MESSAGE_EVENTS_LOCK:
            events = list(MESSAGE_EVENTS)
        if peer:
            events = [ev for ev in events if ev.get("peer") == peer]
        return len(events)


def get_monitor_version() -> int:
    with MONITOR_VERSION_COND:
        return MONITOR_VERSION


def is_monitor_authorized() -> bool:
    if not MONITOR_TOKEN:
        return True
    token = (
        request.args.get("token")
        or request.form.get("token")
        or request.headers.get("X-Monitor-Token")
    )
    return token == MONITOR_TOKEN


def get_monitor_cors_origin() -> str:
    origin = (request.headers.get("Origin") or "").strip()
    if not origin:
        return ""
    if "*" in MONITOR_CORS_ORIGINS:
        return "*"
    if origin in MONITOR_CORS_ORIGINS:
        return origin
    return ""


def bootstrap_monitor_storage() -> None:
    global MONITOR_VERSION
    try:
        init_monitor_db()
        db_version = get_max_monitor_version_from_db()
        with MONITOR_VERSION_COND:
            MONITOR_VERSION = max(MONITOR_VERSION, db_version)
        logger.info("Monitor DB listo path=%s version=%s", MONITOR_DB_PATH, MONITOR_VERSION)
    except Exception as e:
        logger.exception("No se pudo inicializar monitor DB: %s", e)


def extract_text_from_message(message: dict) -> Optional[str]:
    msg_type = message.get("type")

    if msg_type == "text":
        return message.get("text", {}).get("body")

    if msg_type == "interactive":
        interactive = message.get("interactive", {})
        button_reply = interactive.get("button_reply", {})
        list_reply = interactive.get("list_reply", {})

        # ✅ Primero ID (para flujos)
        return (
            button_reply.get("id")
            or list_reply.get("id")
            or button_reply.get("title")
            or list_reply.get("title")
        )

    return None

def send_whatsapp_interactive(to_phone: str, interactive: dict) -> None:
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "interactive",
        "interactive": interactive,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        logger.info("SEND INTERACTIVE -> to=%s status=%s", to_phone, resp.status_code)
        add_monitor_event(
            direction="outbound",
            event_type="interactive",
            peer=to_phone,
            body=str(interactive),
            status="ok" if resp.status_code < 300 else "error",
            detail=f"http={resp.status_code}",
        )
        if resp.status_code >= 300:
            logger.error("GRAPH ERROR (interactive): %s", resp.text)
    except Exception as e:
        add_monitor_event(
            direction="outbound",
            event_type="interactive",
            peer=to_phone,
            body=str(interactive),
            status="exception",
            detail=str(e),
        )
        logger.exception("EXCEPTION sending interactive to=%s err=%s", to_phone, e)

# ========= Spring connector =========
def call_spring(sender: str, text: str, msg_id: str, timestamp: str, phone_number_id: str) -> dict:
    """
    Flask -> Spring
    Espera respuesta:
      {"actions":[{"type":"text","body":"..."}, {"type":"template","name":"...","lang":"es_CO","params":[...]}]}
    """
    url = f"{SPRING_BASE_URL}/api/chatbot/inbound"
    payload = {
        "from": sender,
        "text": text,
        "messageId": msg_id,
        "timestamp": timestamp,
        "phoneNumberId": phone_number_id,
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code >= 300:
            logger.error("SPRING ERROR %s - %s", r.status_code, r.text)
            add_monitor_event(
                direction="system",
                event_type="spring_error",
                peer=sender,
                body=text,
                status="error",
                detail=f"http={r.status_code}",
            )
            return {"actions": [{"type": "text", "body": API_UNAVAILABLE_MESSAGE}]}
        return r.json() if r.content else {"actions": []}
    except Exception as e:
        logger.exception("EXCEPTION calling Spring: %s", e)
        add_monitor_event(
            direction="system",
            event_type="spring_exception",
            peer=sender,
            body=text,
            status="exception",
            detail=str(e),
        )
        return {"actions": [{"type": "text", "body": API_UNAVAILABLE_MESSAGE}]}


# ========= WhatsApp senders =========
def send_whatsapp_text(to_phone: str, body: str) -> None:
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        logger.info("SEND TEXT -> to=%s status=%s", to_phone, resp.status_code)
        add_monitor_event(
            direction="outbound",
            event_type="text",
            peer=to_phone,
            body=body,
            status="ok" if resp.status_code < 300 else "error",
            detail=f"http={resp.status_code}",
        )
        if resp.status_code >= 300:
            logger.error("GRAPH ERROR (text): %s", resp.text)
    except Exception as e:
        add_monitor_event(
            direction="outbound",
            event_type="text",
            peer=to_phone,
            body=body,
            status="exception",
            detail=str(e),
        )
        logger.exception("EXCEPTION sending text to=%s err=%s", to_phone, e)


def send_whatsapp_template(
    to_phone: str,
    template_name: str,
    language_code: str = "es_CO",
    body_params: Optional[List[str]] = None,
) -> None:
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    components = []
    if body_params:
        components.append({
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in body_params],
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": language_code},
            **({"components": components} if components else {}),
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        logger.info("SEND TEMPLATE -> to=%s status=%s", to_phone, resp.status_code)
        add_monitor_event(
            direction="outbound",
            event_type="template",
            peer=to_phone,
            body=template_name,
            status="ok" if resp.status_code < 300 else "error",
            detail=f"http={resp.status_code}",
        )
        if resp.status_code >= 300:
            logger.error("GRAPH ERROR (template): %s", resp.text)
    except Exception as e:
        add_monitor_event(
            direction="outbound",
            event_type="template",
            peer=to_phone,
            body=template_name,
            status="exception",
            detail=str(e),
        )
        logger.exception("EXCEPTION sending template to=%s err=%s", to_phone, e)


# ========= Webhook parsing =========
def iterate_incoming_messages(payload: dict):
    """
    Solo devuelve mensajes reales (value.messages).
    También loguea cambios sin messages (statuses, etc.) para debug.
    """
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            field = change.get("field")
            value = change.get("value", {}) or {}
            msgs = value.get("messages", []) or []

            logger.info("CHANGE field=%s has_messages=%s", field, bool(msgs))

            for msg in msgs:
                yield msg


def extract_phone_number_id(payload: dict) -> str:
    """
    Saca el phone_number_id real desde metadata del payload (si viene).
    """
    try:
        return (
            payload.get("entry", [{}])[0]
            .get("changes", [{}])[0]
            .get("value", {})
            .get("metadata", {})
            .get("phone_number_id", "")
        ) or ""
    except Exception:
        return ""


def dedupe_msg_id(msg_id: Optional[str]) -> bool:
    """
    True => ya lo procesamos (saltar)
    False => nuevo (procesar)
    """
    if not msg_id:
        return False

    if msg_id in PROCESSED_MSG_IDS:
        return True

    PROCESSED_MSG_IDS.add(msg_id)
    if len(PROCESSED_MSG_IDS) > MAX_PROCESSED_CACHE:
        PROCESSED_MSG_IDS.clear()
    return False


def process_webhook_payload(payload: dict) -> None:
    global BOT_PAUSED
    phone_number_id = extract_phone_number_id(payload)

    for message in iterate_incoming_messages(payload):
        msg_id = message.get("id")
        sender = message.get("from")
        msg_type = message.get("type")
        incoming_text = extract_text_from_message(message)
        ts = message.get("timestamp", "")

        if dedupe_msg_id(msg_id):
            logger.info("DEDUP msg_id=%s", msg_id)
            add_monitor_event(
                direction="inbound",
                event_type=msg_type or "unknown",
                peer=sender or "-",
                body=incoming_text,
                status="dedup",
                detail=f"msg_id={msg_id or '-'}",
            )
            continue

        logger.info("INCOMING: from=%s type=%s msg_id=%s text=%s", sender, msg_type, msg_id, incoming_text)
        add_monitor_event(
            direction="inbound",
            event_type=msg_type or "unknown",
            peer=sender or "-",
            body=incoming_text,
            status="ok",
            detail=f"msg_id={msg_id or '-'}",
        )

        if not sender:
            continue

        if not incoming_text:
            send_whatsapp_text(sender, "Te leí ✅. Por ahora solo proceso texto 🙂")
            continue

        if BOT_PAUSED:
            add_monitor_event(
                direction="system",
                event_type="paused_block",
                peer=sender,
                body=incoming_text,
                status="blocked",
                detail="Mensaje procesado con BOT_PAUSED=true",
            )
            send_whatsapp_text(sender, BOT_PAUSED_MESSAGE)
            continue

        # ✅ Primera vez + template (opcional)
        if sender not in SESSIONS and USE_WELCOME_TEMPLATE:
            send_whatsapp_template(
                to_phone=sender,
                template_name=WELCOME_TEMPLATE_NAME,
                language_code=WELCOME_TEMPLATE_LANG,
                body_params=["RutaDigital HARO"],
            )
            # Marca sesión si usas SESSIONS (opcional)
            SESSIONS[sender] = SessionState(step="started")
            continue

        # ✅ Preguntar a Spring qué responder
        spring_out = call_spring(sender, incoming_text, msg_id or "", ts, phone_number_id)
        actions = spring_out.get("actions", []) or []
        logger.info("SPRING actions=%s", len(actions))

        for action in actions:
            a_type = (action.get("type") or "").lower()

            if a_type == "text":
                send_whatsapp_text(sender, action.get("body", ""))

            elif a_type == "template":
                send_whatsapp_template(
                    to_phone=sender,
                    template_name=action.get("name", ""),
                    language_code=action.get("lang", "es_CO"),
                    body_params=action.get("params", []) or [],
                )

            elif a_type == "interactive_list":
                data = action.get("data") or {}
                interactive = {
                    "type": "list",
                    "body": {"text": action.get("body", "")},
                    "action": {
                        "button": data.get("buttonText", "Ver opciones"),
                        "sections": data.get("sections", []),
                    },
                }
                send_whatsapp_interactive(sender, interactive)

            elif a_type == "interactive_buttons":
                data = action.get("data") or {}
                interactive = {
                    "type": "button",
                    "body": {"text": action.get("body", "")},
                    "action": {
                        "buttons": data.get("buttons", []),
                    },
                }
                send_whatsapp_interactive(sender, interactive)

            else:
                send_whatsapp_text(sender, "⚠️ Acción no soportada aún. Escribe *menu*.")

bootstrap_monitor_storage()

# ========= Routes =========
@app.get("/")
def home():
    return "OK - Flask arriba. Prueba /health o /webhook", 200


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "whatsapp-webhook", "version": WHATSAPP_API_VERSION}), 200


@app.get("/webhook")
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge or "", 200
    return "verification failed", 403


@app.get("/api/whatsapp/webhook")
def verify_webhook_api():
    return verify_webhook()


@app.after_request
def apply_monitor_cors_headers(response):
    if request.path in MONITOR_CORS_PATHS:
        allow_origin = get_monitor_cors_origin()
        if allow_origin:
            response.headers["Access-Control-Allow-Origin"] = allow_origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Monitor-Token"
    return response


@app.route("/monitor/events", methods=["OPTIONS"])
@app.route("/api/monitor/events", methods=["OPTIONS"])
@app.route("/monitor/pause", methods=["OPTIONS"])
@app.route("/api/monitor/pause", methods=["OPTIONS"])
def monitor_cors_preflight():
    return "", 204


@app.get("/monitor/events")
@app.get("/api/monitor/events")
def monitor_events():
    if not is_monitor_authorized():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    try:
        since = int((request.args.get("since") or "0").strip())
    except ValueError:
        since = 0

    peer = (request.args.get("peer") or "").strip()
    peer = peer if peer else None

    events = get_monitor_events(since=since, peer=peer)
    return jsonify(
        {
            "ok": True,
            "paused": BOT_PAUSED,
            "count": len(events),
            "total": get_monitor_total_events(peer=peer),
            "version": get_monitor_version(),
            "peer": peer or "",
            "events": events,
        }
    ), 200


@app.get("/monitor/stream")
@app.get("/api/monitor/stream")
def monitor_stream():
    if not is_monitor_authorized():
        return "unauthorized", 401

    try:
        since = int((request.args.get("since") or "0").strip())
    except ValueError:
        since = 0

    def event_stream():
        nonlocal since
        yield "retry: 3000\n\n"
        while True:
            with MONITOR_VERSION_COND:
                if MONITOR_VERSION <= since:
                    MONITOR_VERSION_COND.wait(timeout=20)
                current_version = MONITOR_VERSION

            if current_version > since:
                payload = json.dumps({"version": current_version}, ensure_ascii=False)
                yield f"id: {current_version}\nevent: monitor_update\ndata: {payload}\n\n"
                since = current_version
            else:
                # Mantiene viva la conexion en proxies intermedios.
                yield "event: keepalive\ndata: {}\n\n"

    response = Response(event_stream(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.get("/monitor")
def monitor_dashboard():
    if not is_monitor_authorized():
        return "unauthorized", 401

    token = request.args.get("token", "")
    return render_template(
        "monitor.html",
        token=token,
        poll_seconds=MONITOR_REFRESH_SECONDS,
    )


@app.post("/monitor/pause")
@app.post("/api/monitor/pause")
def monitor_pause():
    if not is_monitor_authorized():
        return "unauthorized", 401

    global BOT_PAUSED
    payload = request.get_json(silent=True) or {}
    action = (
        payload.get("action")
        or request.form.get("action")
        or request.args.get("action")
        or ""
    ).strip().lower()
    if action == "pause":
        BOT_PAUSED = True
    elif action == "resume":
        BOT_PAUSED = False
    else:
        BOT_PAUSED = not BOT_PAUSED

    logger.warning("BOT_PAUSED changed to %s", BOT_PAUSED)
    add_monitor_event(
        direction="system",
        event_type="pause_toggle",
        status="ok",
        detail=f"BOT_PAUSED={BOT_PAUSED}",
    )

    if request.is_json:
        return jsonify({"ok": True, "paused": BOT_PAUSED}), 200

    token = request.form.get("token") or request.args.get("token", "")
    if token:
        return redirect(url_for("monitor_dashboard", token=token))
    return redirect(url_for("monitor_dashboard"))


@app.post("/webhook")
def receive_webhook():
    payload = request.get_json(silent=True) or {}
    logger.info("POST /webhook keys=%s", list(payload.keys()))
    try:
        process_webhook_payload(payload)
    except Exception as e:
        logger.exception("Error procesando /webhook: %s", e)
        add_monitor_event(
            direction="system",
            event_type="webhook_exception",
            status="exception",
            detail=str(e),
        )
    return jsonify({"ok": True}), 200


@app.post("/api/whatsapp/webhook")
def receive_webhook_api():
    payload = request.get_json(silent=True) or {}
    logger.info("POST /api/whatsapp/webhook keys=%s", list(payload.keys()))
    try:
        process_webhook_payload(payload)
    except Exception as e:
        logger.exception("Error procesando /api/whatsapp/webhook: %s", e)
        add_monitor_event(
            direction="system",
            event_type="webhook_exception",
            status="exception",
            detail=str(e),
        )
    return jsonify({"ok": True}), 200


# ========= Main =========
if __name__ == "__main__":
    ok, missing_vars = validate_env()
    if not ok:
        print("Faltan variables de entorno para ejecutar el bot:")
        for var in missing_vars:
            print(f"- {var}")
        raise SystemExit(1)

    port = int(os.getenv("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
