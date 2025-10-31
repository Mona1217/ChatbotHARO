# core/bot.py
from __future__ import annotations

from typing import Dict, Any, Optional
import os
import re

from core.menu import MenuHandler
from storage.session import InMemorySessionStore
from rag.vector_store import VectorStore
from config import settings
from nlu.llm_client import LLMClient

from services.si_client import SIClient


class ChatBotCore:
    def __init__(self):
        self.menu = MenuHandler()
        self.sessions = InMemorySessionStore(ttl_seconds=7200)

        self.vector = VectorStore(settings.KB_PATH)
        self.vector.load()

        self.llm = LLMClient(settings.OPENAI_MODEL)

        # Modo API si hay base URL; de lo contrario, modo DB (QA/local)
        if getattr(settings, "SI_BASE_URL", ""):
            self.provider_mode = "api"
            self.si = SIClient()
        else:
            self.provider_mode = "db"
            self.si = SIClient(base_url="")  # para mocks de email OTP

        # Regex
        self._re_doc = re.compile(r"^(?:doc\s+)?(\d{6,12})$", re.IGNORECASE)
        self._re_otp = re.compile(r"^\d{6}$")
        self._re_email = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

    # ---------------- sesión ----------------
    def _get_state(self, user_id: str) -> Dict[str, Any]:
        st = self.sessions.get(user_id)
        if not st:
            st = {
                "estado": "inicio",
                "auth_id": None,
                "auth_name": None,
                "auth_doc": None,
                "auth_email": None,   # << usamos email para OTP
                "auth_candidate": None,
                "consent_pending": False,
                "_ip": None,
                "_ua": None,
            }
            self.sessions.set(user_id, st)
        return st

    def _save_state(self, user_id: str, state: Dict[str, Any]) -> None:
        self.sessions.set(user_id, state)

    # ------------- render -------------
    def _render_dashboard_si(self, dash: dict, full_name: str, doc: str) -> str:
        nxt = dash.get("next")
        rec = dash.get("recent", [])
        saldo = dash.get("saldo")
        estado_c = dash.get("estado_cuenta")

        lines = [f"👤 *{full_name}* (Doc: {doc})"]
        if nxt:
            lines.append(
                f"📅 Próxima: {nxt.get('fecha')} {nxt.get('hora_inicio')}–{nxt.get('hora_fin')}"
                f" · {nxt.get('estado','')}"
                f" · Prof: {nxt.get('profesor','')}"
                f" · Veh: {nxt.get('placa_vehiculo','')}"
            )
        else:
            lines.append("📅 Próxima: (no registrada)")

        if rec:
            lines.append("\n🗂️ Últimas 3 clases:")
            for r in rec[:3]:
                lines.append(
                    f"• {r.get('fecha')} {r.get('hora_inicio')}–{r.get('hora_fin')}"
                    f" · {r.get('estado','')}"
                    f" · Prof: {r.get('profesor','')}"
                    f" · Veh: {r.get('placa_vehiculo','')}"
                )
        else:
            lines.append("\n🗂️ Últimas 3 clases: (sin registros)")

        if saldo is not None:
            try:
                monto = f"{int(round(float(saldo))):,}".replace(",", ".")
            except Exception:
                monto = str(saldo)
            lines.append(f"\n💳 Saldo: ${monto} · Estado: {estado_c or '-'}")

        lines.append("\nComandos: *mi_info* · *politica* · *volver*")
        return "\n".join(lines)

    # ------------- puente API/DB -------------
    def _get_student_by_doc(self, doc: str) -> Optional[Dict[str, Any]]:
        try:
            return self.si.get_student_by_document(doc)
        except Exception:
            return {"_api_error": True}

    def _get_dashboard(self, id_est: int | str) -> dict:
        if self.provider_mode == "api":
            return self.si.get_student_dashboard(id_est)
        else:
            return 

    # ------------- textos -------------
    def _msg_politica(self) -> str:
        return (
            "🛡️ *Tratamiento de datos*\n"
            "Usaremos tus datos para matrícula, agendamiento y contacto, conforme a la normatividad vigente.\n"
            "Si estás de acuerdo, responde: *acepto*\n"
            "Para más info escribe: *politica*"
        )

    def _msg_pedir_doc(self) -> str:
        return (
            "🔐 *Verificación de identidad*\n"
            "Escribe tu número de *cédula* así:\n"
            "• *doc 1094XXXXXX*  o solo envía el *número*.\n"
            "Buscaremos tu correo registrado y te enviaremos un *OTP*."
        )

    def _msg_pedir_email(self) -> str:
        return (
            "📧 No encontré un correo asociado o falta en tu registro.\n"
            "Por favor escribe tu *correo electrónico* para enviarte el código (ej.: usuario@dominio.com)."
        )

    # ------------- RAG / LLM -------------
    def _rag_answer(self, query: str) -> str:
        hits = self.vector.search(query, k=3)
        snippets = []
        for t, src in hits:
            snippets.append(f"- {t[:220]}... (src: {os.path.basename(src)})")
        if not snippets:
            system = (
                "Eres un asesor amable de una academia de conducción en Colombia. "
                "Responde breve, claro y con pasos concretos."
            )
            return self.llm.generate(
                f"Pregunta del usuario: {query}\nResponde en menos de 80 palabras.",
                system=system,
            )
        return "\n".join(snippets)

    # ------------- MAIN -------------
    def handle_message(self, user_id: str, text: str) -> str:
        state = self._get_state(user_id)
        estado_actual = state.get("estado", "inicio")

        entrada_raw = (text or "").strip()
        entrada = entrada_raw.lower()

        # Globales
        if entrada in {"menu", "inicio", "start"}:
            state["estado"] = "inicio"
            self._save_state(user_id, state)
            return self.menu.menus["inicio"]["mensaje"]

        if entrada == "politica":
            return (
                "🛡️ *Política de Tratamiento de Datos*\n"
                "Autorizas el uso de tus datos para matrícula, agendamiento y contacto según la ley aplicable.\n"
                "Si estás de acuerdo, escribe: *acepto*."
            )

        # Consentimiento
        if entrada == "acepto" and state.get("estado") != "politica_activo":
            if not state.get("auth_id"):
                state["estado"] = "politica_activo"
                state["consent_pending"] = True
                self._save_state(user_id, state)
                return self._msg_politica()
            # Si ya está autenticado, registra ahora (si tienes endpoint de consent)
            return "✅ Consentimiento registrado."

        if estado_actual == "politica_activo" and entrada == "acepto":
            state["consent_pending"] = True
            state["estado"] = "login_estudiante"
            self._save_state(user_id, state)
            return self._msg_pedir_doc()

        # Menú → transición base
        respuesta_menu, nuevo_estado = self.menu.siguiente(estado_actual, entrada)

        # Forzar política si va a 'activo' sin consent
        if nuevo_estado == "activo" and not state.get("consent_pending") and not state.get("auth_id"):
            state["estado"] = "politica_activo"
            self._save_state(user_id, state)
            return self._msg_politica()

        # Si ya está en 'activo' y pide autenticar
        if nuevo_estado == "activo" and entrada in {"autenticar", "login"}:
            if not state.get("consent_pending") and not state.get("auth_id"):
                state["estado"] = "politica_activo"
                self._save_state(user_id, state)
                return self._msg_politica()
            else:
                state["estado"] = "login_estudiante"
                self._save_state(user_id, state)
                return self._msg_pedir_doc()

        # ---- LOGIN ESTUDIANTE (doc → obtenemos email → send OTP) ----

        if estado_actual == "login_estudiante" or nuevo_estado == "login_estudiante":
            state["estado"] = "login_estudiante"
            self._save_state(user_id, state)

            clean = entrada_raw.strip().replace(".", "").replace("-", "")
            m = self._re_doc.match(clean)
            if m:
                doc = m.group(1)

                # ✅ No hay búsqueda por cédula en el SI: guardamos doc y pedimos email
                state["auth_candidate"] = {
                    "id": doc,                 # por ahora usamos doc como id lógico de sesión
                    "nombre": "Estudiante",    # si luego tienes nombre, lo actualizas
                    "doc": doc
                }
                state["estado"] = "login_pedir_email"
                self._save_state(user_id, state)
                return self._msg_pedir_email()

            # Si aún no mandó doc, repetir instrucción
            return self._msg_pedir_doc()


        # ---- PEDIR EMAIL MANUALMENTE Y ENVIAR OTP ----
        if estado_actual == "login_pedir_email":
            if not self._re_email.match(entrada_raw):
                return "Formato de correo no válido. Ejemplo: usuario@dominio.com"
            email = entrada_raw.strip()

            ok = self.si.send_email_otp(email)
            if not ok:
                return "⚠️ No pude enviar el código a ese correo. Verifica el correo o intenta más tarde."

            state["auth_email"] = email
            state["estado"] = "verificar_otp_email"
            self._save_state(user_id, state)
            return f"📨 Enviamos un código de 6 dígitos a *{self._mask_email(email)}*. Responde: *otp 123456*"

        # ---- VERIFICAR OTP (por email) ----
        if estado_actual == "verificar_otp_email":
            if entrada.startswith("otp "):
                code = entrada_raw.split(" ", 1)[1].strip()
                if not self._re_otp.match(code):
                    return "OTP inválido. Debe ser un código de *6 dígitos*."
                email = state.get("auth_email")
                cand = state.get("auth_candidate") or {}
                if not email or not cand:
                    state["estado"] = "login_estudiante"
                    self._save_state(user_id, state)
                    return "⚠️ No hay autenticación en curso. Envía tu documento: *doc 1094XXXXXX*"

                ok = self.si.verify_email_otp(email, code)
                if not ok:
                    return "❌ Código inválido o vencido. Intenta de nuevo. (Ej: *otp 123456*)"

                # Autenticado
                state["auth_id"] = cand.get("id")
                state["auth_name"] = cand.get("nombre", "Estudiante")
                state["auth_doc"] = cand.get("doc")
                state["estado"] = "activo"
                self._save_state(user_id, state)

                dash = self._get_dashboard(state["auth_id"])
                return self._render_dashboard_si(dash, state["auth_name"], state["auth_doc"])
            else:
                return "Ingresa tu código así: *otp 123456*"

        # ---- mi_info ----
        if entrada in {"mi_info", "info"}:
            if not state.get("auth_id"):
                state["estado"] = "politica_activo"
                self._save_state(user_id, state)
                return self._msg_politica()
            dash = self._get_dashboard(state["auth_id"])
            return self._render_dashboard_si(dash, state.get("auth_name", "Estudiante"), state.get("auth_doc", ""))

        # ---- resto del flujo por menú + IA ----
        state["estado"] = nuevo_estado
        self._save_state(user_id, state)
        respuesta_final = respuesta_menu

        opciones = self.menu.menus.get(estado_actual, {}).get("transiciones", {})
        if entrada and entrada not in opciones:
            ctx = self._rag_answer(entrada_raw)
            if ctx:
                respuesta_final = f"{respuesta_final}\n\n🤖 *IA te sugiere:*\n{ctx}"

        return respuesta_final

    # ---------------- utils ----------------
    @staticmethod
    def _mask_email(email: str) -> str:
        try:
            name, domain = email.split("@", 1)
            nm = name[:2] + ("*" * max(0, len(name) - 2))
            dom, *tld = domain.split(".")
            dm = dom[:2] + ("*" * max(0, len(dom) - 2))
            return f"{nm}@{dm}" + (("." + ".".join(tld)) if tld else "")
        except Exception:
            return email
