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
WHATSAPP_APP_SECRET=tu_app_secret_de_meta
WHATSAPP_API_VERSION=v24.0
PORT=8000
SPRING_BASE_URL=https://tu-backend-spring.run.app/
SPRING_AUTH_URL=https://tu-backend-spring.run.app/api/auth/login
SPRING_AUTH_BODY_JSON={"email":"tu_usuario","password":"tu_password"}
SPRING_AUTH_TOKEN_JSON_PATH=token
SPRING_AUTH_HEADER_NAME=Authorization
SPRING_AUTH_HEADER_PREFIX=Bearer 
CHATBOT_ENROLLMENT_WELCOME_IMAGE_URL=https://haro-files.s3.us-east-2.amazonaws.com/clases/clase-1/imagen/2026/03/saludo-bot.jpeg
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
- Exportar numeros a Excel: `GET /monitor/export/contacts.xlsx`
- Boton de pausa/reanudar: `POST /monitor/pause` (desde el mismo panel)
- Frontend del monitor (estilo WhatsApp simulado): `templates/monitor.html` + `static/monitor.css` + `static/monitor.js`

Variables opcionales:
```env
MONITOR_TOKEN=un_token_para_proteger_monitor
MONITOR_USERNAME=admin
MONITOR_PASSWORD=cambia_esta_contrasena
APP_SESSION_SECRET=una_clave_larga_y_privada
MONITOR_LOG_MAX=0
WEBHOOK_JOB_HISTORY_LIMIT=1000
MONITOR_DB_PATH=monitor_events.db
MONITOR_CORS_ORIGINS=https://tu-frontend.com,http://127.0.0.1:8080,http://localhost:8080
BOT_PAUSED=false
BOT_PAUSED_MESSAGE=En este momento no estoy disponible, intenta mas tarde.
CHATBOT_ENROLLMENT_WELCOME_IMAGE_URL=
CHATBOT_ENROLLMENT_WELCOME_IMAGE_CAPTION=
```

Notas:
- `MONITOR_LOG_MAX=0` guarda todo el historial en memoria (sin recorte).
- `WEBHOOK_JOB_HISTORY_LIMIT=1000` conserva una ventana de jobs del webhook ya procesados para que la cola persistente no crezca sin limite.
- `MONITOR_DB_PATH` persiste eventos para conservar conversaciones por usuario tras reinicios. Si dejas una ruta relativa, ahora se resuelve contra la carpeta del proyecto.
- `WHATSAPP_APP_SECRET` permite validar la firma `X-Hub-Signature-256` de Meta. Si la defines, el webhook rechazara payloads no firmados o alterados.
- Si defines `MONITOR_USERNAME` y `MONITOR_PASSWORD`, la pagina del monitor mostrara un login visual antes de entrar.
- `APP_SESSION_SECRET` protege la sesion del login del monitor.
- Si tu backend Spring requiere login previo, define `SPRING_AUTH_BODY_JSON` con el body JSON del `POST /api/auth/login`.
- `SPRING_AUTH_TOKEN_JSON_PATH` indica en que campo viene el token. Ejemplos: `token`, `accessToken`, `data.token`.
- Si defines `MONITOR_TOKEN`, abre el panel asi: `/monitor?token=TU_TOKEN`.
- Si abres el monitor desde otro puerto local como `127.0.0.1:8080`, agrega ese origen a `MONITOR_CORS_ORIGINS`.
- En estado `PAUSADO`, el bot no consulta Spring y responde `BOT_PAUSED_MESSAGE`.
- El estado `PAUSADO` ahora tambien queda persistido en la DB del monitor y sobrevive reinicios.
- Si defines `CHATBOT_ENROLLMENT_WELCOME_IMAGE_URL`, la primera respuesta a cada usuario será una imagen.

- El boton `Exportar Excel` descarga los numeros unicos con los que el bot se ha comunicado, junto con primer/ultimo contacto y conteos de eventos.

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

## 7) Docker + Render
Build local:
```bash
docker build -t whatsapp-flow-bot .
docker run --rm -p 8000:8000 --env-file .env whatsapp-flow-bot
```

Deploy en Render:
1. Sube este repo a GitHub.
2. En Render, crea el servicio con `Blueprint` para que tome `render.yaml` automaticamente.
3. El blueprint ya deja el servicio listo con Docker, `healthCheckPath=/health`, `PORT=10000`, una sola instancia, PR previews en modo manual y un disco persistente en `/var/data`.
4. La base del monitor queda persistente en Render usando `MONITOR_DB_PATH=/var/data/monitor_events.db`, asi que no se pierden chats ni la exportacion de Excel al reiniciar o redesplegar.
5. El blueprint tambien genera automaticamente `MONITOR_TOKEN` para proteger el panel y la exportacion.
   Lo encuentras en la seccion `Environment` del servicio ya desplegado.
   Si prefieres una pantalla de login, configura tambien `MONITOR_USERNAME` y `MONITOR_PASSWORD`.
6. Completa en Render las variables secretas obligatorias:
   - `WHATSAPP_VERIFY_TOKEN`
   - `WHATSAPP_ACCESS_TOKEN`
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_APP_SECRET`
7. Si tu backend de Spring cambia, actualiza `SPRING_BASE_URL`.
   Si necesita autenticacion, ajusta tambien `SPRING_AUTH_URL`, `SPRING_AUTH_BODY_JSON` y `SPRING_AUTH_TOKEN_JSON_PATH`.
8. Usa la URL publica de Render para el webhook de Meta:
   - Verificacion: `GET https://TU-SERVICIO.onrender.com/webhook`
   - Mensajes entrantes: `POST https://TU-SERVICIO.onrender.com/webhook`
9. El monitor quedara disponible en:
   - `https://TU-SERVICIO.onrender.com/monitor?token=TU_MONITOR_TOKEN`
   - `https://TU-SERVICIO.onrender.com/monitor/export/contacts.xlsx?token=TU_MONITOR_TOKEN`

Notas de Render:
- El disco persistente es la pieza clave para que el monitor y la exportacion mantengan historial.
- Si no usas el blueprint, replica manualmente estas dos cosas en Render: disco montado en `/var/data` y `MONITOR_DB_PATH=/var/data/monitor_events.db`.
