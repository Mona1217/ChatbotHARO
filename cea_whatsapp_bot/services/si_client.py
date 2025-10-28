# services/si_client.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any, List

import requests
from requests.auth import HTTPBasicAuth


class SIClient:
    """
    Cliente del Sistema de Información (SI) para el bot.

    Variables de entorno soportadas:
      - SI_BASE_URL       (p. ej. http://localhost:8081)
      - SI_USER / SI_PASS (opcional, Basic Auth)
      - SI_TIMEOUT        (segundos, por defecto 10)

    Endpoints relevantes (según tu API):
      - GET  /api/estudiantes?documento=XXXX     → buscar estudiante y obtener email
      - POST /api/verification/email/send        → {email}
      - POST /api/verification/email/verify      → {email, code}
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user: Optional[str] = None,
        pwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url: str = (base_url or os.getenv("SI_BASE_URL", "")).rstrip("/")
        self.timeout: int = int(timeout or os.getenv("SI_TIMEOUT", "10"))

        _user = user or os.getenv("SI_USER", "")
        _pass = pwd or os.getenv("SI_PASS", "")
        self.auth = HTTPBasicAuth(_user, _pass) if (_user or _pass) else None

        self.s = requests.Session()
        if self.auth:
            self.s.auth = self.auth
        self.s.headers.update({"Accept": "application/json"})

    # ----------------------------
    # Utilidades internas
    # ----------------------------
    def _url(self, path: str) -> str:
        if not self.base_url:
            return path
        return f"{self.base_url}{'' if path.startswith('/') else '/'}{path}"

    def _get(self, path: str, **kwargs) -> requests.Response:
        if not self.base_url:
            raise RuntimeError("SIClient en modo MOCK: define SI_BASE_URL para llamadas reales.")
        return self.s.get(self._url(path), timeout=self.timeout, **kwargs)

    def _post(self, path: str, **kwargs) -> requests.Response:
        if not self.base_url:
            raise RuntimeError("SIClient en modo MOCK: define SI_BASE_URL para llamadas reales.")
        return self.s.post(self._url(path), timeout=self.timeout, **kwargs)

    # ----------------------------
    # Estudiantes
    # ----------------------------
    def get_student_by_document(self, numero_documento: str) -> Optional[Dict[str, Any]]:

        if not self.base_url:
            doc = str(numero_documento)
            if doc.startswith("1094"):
                return {
                    "id_estudiante": 101,
                    "nombre": "Daniela",
                    "apellido": "Piñeros",
                    "email": "daniela.pineros@ejemplo.com",
                    "numero_documento": doc,
                }
            if doc.startswith("123"):
                return {
                    "id_estudiante": 202,
                    "nombre": "Carlos",
                    "apellido": "Ramírez",
                    "email": None,  # sin email para forzar pedirlo
                    "numero_documento": doc,
                }
            return None

        try:
            r = self._get("/api/estudiantes", params={"documento": numero_documento})
        except requests.HTTPError as e:
            if getattr(e.response, "status_code", None) == 401:
                return {"_auth_error": True}
            raise

        if r.status_code == 401:
            return {"_auth_error": True}
        if r.status_code == 404:
            return None
        r.raise_for_status()

        data = r.json()

        def _map_item(item: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "id_estudiante": item.get("id") or item.get("id_estudiante"),
                "nombre": item.get("nombre") or item.get("full_name"),
                "apellido": item.get("apellido"),
                "email": item.get("email"),
                "numero_documento": item.get("numeroDocumento") or item.get("numero_documento"),
            }

        if isinstance(data, dict) and data:
            mapped = _map_item(data)
            if str(mapped.get("numero_documento")) == str(numero_documento):
                return mapped
            return None

        if isinstance(data, list):
            for item in data:
                nd = item.get("numeroDocumento") or item.get("numero_documento")
                if str(nd) == str(numero_documento):
                    return _map_item(item)
            return None

        return None

    # ----------------------------
    # VERIFICACIÓN POR EMAIL (OTP)
    # ----------------------------
    def send_email_otp(self, email: str) -> bool:
        """
        POST /api/verification/email/send  {email}
        Devuelve True si pudo disparar el correo, False en 401/400/5xx.
        """
        if not email:
            return False

        if not self.base_url:
            # MOCK: como si hubiera enviado el correo
            return True

        try:
            r = self._post("/api/verification/email/send", json={"email": email})
        except Exception:
            return False

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {}
            return bool(data.get("ok", True))
        if r.status_code in (400, 401, 500):
            return False

        try:
            r.raise_for_status()
        except Exception:
            return False
        return False

    def verify_email_otp(self, email: str, code: str) -> bool:
        """
        POST /api/verification/email/verify  {email, code}
        True si verified=true, de lo contrario False.
        """
        if not email or not code:
            return False

        if not self.base_url:
            # MOCK: acepta siempre "000000" para demo
            return code == "000000"

        try:
            r = self._post("/api/verification/email/verify", json={"email": email, "code": code})
        except Exception:
            return False

        if r.status_code == 200:
            try:
                data = r.json()
            except Exception:
                data = {}
            return bool(data.get("verified", False))
        if r.status_code in (400, 401, 500):
            return False

        try:
            r.raise_for_status()
        except Exception:
            return False
        return False

    # ----------------------------
    # (Opcional) Dashboard u otros
    # ----------------------------
    def get_student_dashboard(self, id_est: int | str) -> Dict[str, Any]:
        """
        Si lo necesitas para 'mi_info'. Mantengo este método como antes.
        """
        if not self.base_url:
            # MOCK básico
            return {
                "next": None,
                "recent": [],
                "saldo": 0,
                "estado_cuenta": "al_dia",
            }
        r = self._get(f"/api/estudiantes/{id_est}/dashboard")
        r.raise_for_status()
        return r.json()
