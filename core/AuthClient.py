# AuthClient.py
import requests

BACKEND_URL = "http://localhost:8081"
SYSTEM_JWT = "<TOKEN_DEL_SISTEMA>"

class AuthClient:
    @staticmethod
    def enviar_codigo(email: str) -> bool:
        url = f"{BACKEND_URL}/api/auth/request-email-code"
        payload = {
            "email": email,
            "purpose": "verificacion_identidad"
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SYSTEM_JWT}"
        }

        r = requests.post(url, json=payload, headers=headers, timeout=5)
        data = r.json()
        return data.get("ok", False)
