# services/si_client.py
from __future__ import annotations

import os
from typing import Optional, Dict, Any

import requests
from requests.auth import HTTPBasicAuth


class SIClient:
    """
    Cliente del Sistema de Informacion (SI) para el bot.

    Variables de entorno soportadas:
      - SI_BASE_URL            (p. ej. http://localhost:8081)
      - SI_USER / SI_PASS      (opcional, Basic Auth)
      - SI_BEARER_TOKEN        (opcional, Authorization: Bearer ...)
      - SI_TIMEOUT             (segundos, por defecto 10)

    Endpoints relevantes (segun tu API):
      - GET  /api/estudiantes?documento=XXXX     → buscar estudiante (si existiera)
      - POST /api/verification/email/send        → {email}
      - POST /api/verification/email/verify      → {email, code}
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        user: Optional[str] = None,
        pwd: Optional[str] = None,
        timeout: Optional[int] = None,
        bearer_token: Optional[str] = None,
    ):
        self.base_url: str = (base_url or os.getenv("SI_BASE_URL", "")).rstrip("/")
        self.timeout: int = int(timeout or os.getenv("SI_TIMEOUT", "10"))

        # Preferimos Bearer si existe; si no, Basic; si ninguno, sin auth.
        token = bearer_token or os.getenv("SI_BEARER_TOKEN", "").strip()
        _user = user or os.getenv("SI_USER", "")
        _pass = pwd or os.getenv("SI_PASS", "")

        self.s = requests.Session()
        self.s.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

        if token:
            self.s.headers["Authorization"] = f"Bearer {token}"
            self.auth = None
        elif _user or _pass:
            self.auth = HTTPBasicAuth(_user, _pass)
            self.s.auth = self.auth
        else:
            self.auth = None  # sin auth

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
    # PING / Pre-flight
    # ----------------------------
    def check_connectivity(self) -> tuple[bool, str]:
        """
        Verifica conectividad y autenticacion contra el SI.
        Estrategia:
          A) GET /actuator/health (si existe) -> 200/204 = OK
          B) POST /api/verification/email/send {}:
             - 200/400/422 = autenticacion aceptada (OK)
             - 401/403 = auth mala (FAIL)
        """
        # A) actuator/health (si esta habilitado)
        try:
            r = self.s.get(f"{self.base_url}/actuator/health", timeout=5)
            if r.status_code in (200, 204):
                return True, f"OK actuator/health -> {r.status_code}"
            # si 401/403/404 seguimos con B
        except Exception:
            pass

        # B) /verification/email/send con body vacio
        try:
            r = self.s.post(
                f"{self.base_url}/api/verification/email/send",
                json={},
                timeout=5
            )
            sc = r.status_code
            if sc in (200, 400, 422):
                return True, f"Auth OK (status {sc}) en /verification/email/send"
            if sc in (401, 403):
                return False, f"Auth FAIL (status {sc}) en /verification/email/send"
            return True, f"Conectado (status {sc}) en /verification/email/send"
        except requests.exceptions.ConnectionError as ex:
            return False, f"Sin conexion a {self.base_url}: {ex}"
        except Exception as ex:
            return False, f"Error al verificar: {type(ex).__name__}: {ex}"

    # ----------------------------
    # Estudiantes (si tu API lo tuviera)
    # ----------------------------
    def get_student_by_document(self, numero_documento: str) -> Optional[Dict[str, Any]]:
        """
        Solo util si tu SI expone GET /api/estudiantes?documento=...
        Si no existe, puedes ignorar este metodo en el flujo.
        """
        if not self.base_url:
            # MOCK simple para demo local
            doc = str(numero_documento)
            if doc.startswith("1094"):
                return {
                    "id_estudiante": 101,
                    "nombre": "Daniela",
                    "apellido": "Pineros",
                    "email": "daniela.pineros@ejemplo.com",
                    "numero_documento": doc,
                }
            if doc.startswith("123"):
                return {
                    "id_estudiante": 202,
                    "nombre": "Carlos",
                    "apellido": "Ramirez",
                    "email": None,
                    "numero_documento": doc,
                }
            return None

        r = self._get("/api/estudiantes", params={"documento": numero_documento})
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
    # VERIFICACION POR EMAIL (OTP)
    # ----------------------------
    def send_email_otp(self, email: str) -> bool:
        """
        POST /api/verification/email/send  {email}
        True si puede disparar correo; False si 401/400/5xx o error.
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
        if r.status_code in (400, 401, 403, 500):
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
        if r.status_code in (400, 401, 403, 500):
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
        Si lo necesitas para 'mi_info'. Mantengo este metodo como antes.
        """
        if not self.base_url:
            # MOCK basico
            return {
                "next": None,
                "recent": [],
                "saldo": 0,
                "estado_cuenta": "al_dia",
            }
        r = self._get(f"/api/estudiantes/{id_est}/dashboard")
        r.raise_for_status()
        return r.json()
