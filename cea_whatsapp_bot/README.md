# Academia de Conducción – Chatbot WhatsApp (Flask + Twilio + IA + RAG)

## 1) Requisitos
- Python 3.10+
- Cuenta de Twilio (o WhatsApp Business Cloud) y número/sandbox de WhatsApp
- (Opcional) OpenAI API Key para respuestas IA
- (Opcional) Redis si deseas sesiones persistentes

## 2) Instalación
```bash
python -m venv .venv
source .venv/bin/activate  # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edita .env con tus claves
```

## 3) Ejecutar local
```bash
python app.py
```
Prueba HTTP local:
```bash
curl -X POST http://localhost:5000/chat -H "Content-Type: application/json" -d '{"user_id":"u1","mensaje":"inicio"}'
```

## 4) Conectar con WhatsApp (Twilio)
1. En Twilio, activa *WhatsApp Sandbox* o tu número habilitado.
2. En *Sandbox Configuration*, establece el *When a message comes in* a tu URL pública `https://<dominio>/whatsapp`.
3. Para exponer tu servidor local usa *ngrok*:
   ```bash
   # instala ngrok y autentícalo (ngrok config add-authtoken <token>)
   ngrok http 5000
   ```
   Copia la URL que te da (por ejemplo `https://ab12-34-56-78.ngrok-free.app`) y pégala en Twilio.
4. Envia un WhatsApp al número del sandbox con el *join code* que Twilio te muestra y prueba escribiendo *inicio*.

## 5) Flujo de menús (resumen)
- `inicio` → Nuevo / Activo
- `nuevo` → info_cursos / costos / matricula
- `activo` → agendar_practica / examen_teorico / certificados

Cada pantalla acepta *volver* y texto libre: en ese caso intentamos RAG sobre `knowledge_base/` y, si no hay match, LLM (OpenAI).

## 6) “Autoaprendizaje” realista
- Guarda conversaciones/anotaciones en `logs/` (o una BD). Identifica *preguntas frecuentes* y añade notas a `knowledge_base/`.
- Semanalmente re-crea el índice de embeddings (ya se genera al iniciar). Puedes automatizar una tarea cron.
- Para entrenamiento real: exporta pares (pregunta, respuesta esperada) y afina un modelo supervisado o usa *Assistants* con *knowledge files*.
- Implementa *feedback* por parte del usuario (e.g., “¿te fue útil? (sí/no)”) y usa ese label para priorizar mejoras.

## 7) Estructura
```
core/
  bot.py           # orquestador
  menu.py          # estados y transiciones
knowledge_base/    # .md usados por RAG
nlu/
  llm_client.py    # OpenAI (opcional)
rag/
  vector_store.py  # FAISS + SentenceTransformers
storage/
  session.py       # sesiones en memoria (reemplaza por Redis en prod)
app.py             # Flask + webhook Twilio
```

## 8) Seguridad y datos
- Informa tratamiento de datos y política de privacidad en el primer mensaje (o bajo comando *política*).
- Registra consentimientos cuando el usuario avanza a *matrícula*.
- No logues documentos sensibles en claro; usa cifrado/almacenamiento seguro.

## 9) Próximos pasos sugeridos
- Persistir sesiones en Redis; capturar *nombre/documento* en `matricula` y guardarlo en una DB.
- Validación de identidad: integra OCR (Google Vision / AWS Textract) para leer cédula y confirmar coincidencia.
- Agenda real: conectarse a Google Calendar o una tabla propia para slots disponibles.
```

