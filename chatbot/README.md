# Chatbot en Python para WhatsApp

Este proyecto usa `whatsapp_flow_bot.py` como bot de WhatsApp con flujo guiado.

## 1) Instalar dependencias
```bash
python -m pip install -r requirements.txt
```

## 2) Variables de entorno
1. Crea `.env` copiando `.env.example`
2. Completa los valores de WhatsApp Cloud API

```env
WHATSAPP_VERIFY_TOKEN=un_token_que_tu_elijas
WHATSAPP_ACCESS_TOKEN=pega_aqui_tu_access_token_permanente
WHATSAPP_PHONE_NUMBER_ID=tu_phone_number_id
WHATSAPP_API_VERSION=v24.0
PORT=8000
```

## 3) Ejecutar bot de WhatsApp
```bash
python whatsapp_flow_bot.py
```

Webhook local:
- Verificacion: `GET /webhook`
- Mensajes entrantes: `POST /webhook`

## 4) Monitoreo web del bot
- Panel: `GET /monitor`
- Eventos JSON: `GET /monitor/events`
- Boton de pausa/reanudar: `POST /monitor/pause` (desde el mismo panel)
- Frontend del monitor (estilo WhatsApp simulado): `templates/monitor.html` + `static/monitor.css` + `static/monitor.js`

Variables opcionales:
```env
MONITOR_TOKEN=un_token_para_proteger_monitor
MONITOR_LOG_MAX=0
MONITOR_DB_PATH=monitor_events.db
BOT_PAUSED=false
BOT_PAUSED_MESSAGE=En este momento no estoy disponible, intenta mas tarde.
```

Notas:
- `MONITOR_LOG_MAX=0` guarda todo el historial en memoria (sin recorte).
- `MONITOR_DB_PATH` persiste eventos para conservar conversaciones por usuario tras reinicios.
- Si defines `MONITOR_TOKEN`, abre el panel asi: `/monitor?token=TU_TOKEN`.
- En estado `PAUSADO`, el bot no consulta Spring y responde `BOT_PAUSED_MESSAGE`.

## 5) Flujo conversacional actual
1. Pide nombre.
2. Pide correo.
3. Pide opcion (`1/2/3`).
4. Pide confirmacion (`1` confirmar, `2` reiniciar).
5. Marca solicitud como registrada.

Comando para reiniciar flujo: `menu`

## 6) Datos que debes pasarme para dejarlo 100% conectado
- `WHATSAPP_ACCESS_TOKEN` (permanente, no temporal).
- `WHATSAPP_PHONE_NUMBER_ID`.
- `WHATSAPP_VERIFY_TOKEN` (el mismo valor que pongas en Meta Webhooks).
- URL publica del webhook (si usas local, por ejemplo con ngrok).
