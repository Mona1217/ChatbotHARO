from __future__ import annotations
import os
from dotenv import load_dotenv

# Load .env
load_dotenv()

class Settings:
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    PORT = int(os.getenv("PORT", "5000"))
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "whatsapp:+14155238886")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "sentence-transformers")
    REDIS_URL = os.getenv("REDIS_URL", "")
    DATABASE_URL = os.getenv("DATABASE_URL")  
    PROJECT_NAME = "Academia de Conducción Bot"
    KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base")
    LOGS_PATH = os.path.join(os.path.dirname(__file__), "logs")

    SI_BASE_URL = os.getenv("SI_BASE_URL")
    SI_USER = os.getenv("SI_USER")
    SI_PASS = os.getenv("SI_PASS")

    QA_BYPASS_OTP = os.getenv("QA_BYPASS_OTP", "0") in ("1", "true", "True")


settings = Settings()

os.makedirs(settings.KB_PATH, exist_ok=True)
os.makedirs(settings.LOGS_PATH, exist_ok=True)
