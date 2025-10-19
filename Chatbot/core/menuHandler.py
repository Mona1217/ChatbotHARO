import re
import random
from datetime import datetime

class MenuHandler:
    """
    Manejador de flujo conversacional optimizado para WhatsApp.
    - Interfaz: procesar_opcion(estado_actual, entrada_usuario) -> (respuesta, nuevo_estado)
    - set_user(wa_from): guarda el número del usuario (ej. 'whatsapp:+57...')
    - send_otp_callback: función inyectada para enviar el OTP por WhatsApp
    """

    EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

    def __init__(self, send_otp_callback=None):
        # callback para enviar OTP: def cb(to_number: str, body: str) -> None
        self.send_otp_callback = send_otp_callback

        # Estado de sesión simple (por instancia/usuario)
        self.session = {
            "wa_from": None,  # 'whatsapp:+57XXXXXXXXXX'
            "matricula": {
                "nombre": None,
                "correo": None,
                "tc_aceptados": False,
                "otp": None,
                "otp_intentos": 0
            },
            "ultimo_curso": None
        }

        self.mensajes = {
            "inicio": (
                "👋 *Bienvenido a la Academia de Conducción*\n\n"
                "Elige una opción:\n"
                "1️⃣ *Nuevo estudiante* (info o matrícula)\n"
                "2️⃣ *Estudiante activo*\n\n"
                "📌 Escribe *ayuda* en cualquier momento."
            ),
            "ayuda": (
                "🆘 *Ayuda*\n"
                "• Usa *1*, *2* o palabras como 'nuevo', 'activo'.\n"
                "• *menu* o *inicio* te lleva al comienzo.\n"
                "• *volver* regresa un paso atrás."
            ),
            "menu_nuevo_estudiante": (
                "🆕 *Nuevo estudiante*\n"
                "1️⃣ Ver información de cursos\n"
                "2️⃣ Iniciar matrícula\n"
                "3️⃣ Volver al inicio"
            ),
            "menu_estudiante_activo": (
                "🎓 *Estudiante activo*\n"
                "1️⃣ Agendar clase práctica\n"
                "2️⃣ Programar examen teórico\n"
                "3️⃣ Solicitar certificación\n"
                "4️⃣ Información general de cursos\n"
                "5️⃣ Volver al inicio"
            ),
            "menu_cursos": (
                "📚 *Cursos disponibles*\n"
                "A) Carro 🚗\n"
                "B) Moto 🏍️\n"
                "C) Reentrenamiento 🔁\n\n"
                "Escribe *A*, *B*, *C* o *volver*."
            ),
            "curso_carro": (
                "🚗 *Curso Carro Particular*\n"
                "• Teoría + práctica\n"
                "• Horarios flexibles\n"
                "• Certificación válida\n\n"
                "Escribe *matricularme* para iniciar la matrícula o *volver*."
            ),
            "curso_moto": (
                "🏍️ *Curso Moto*\n"
                "• Enfoque en seguridad vial\n"
                "• Prácticas guiadas\n\n"
                "Escribe *matricularme* para iniciar la matrícula o *volver*."
            ),
            "curso_reentrenamiento": (
                "🔁 *Reentrenamiento*\n"
                "• Actualización normativa\n"
                "• Evaluación de habilidades\n\n"
                "Escribe *matricularme* para iniciar la matrícula o *volver*."
            ),
            "form_nombre": "📝 Empecemos tu matrícula. Escribe tu *nombre completo*.",
            "form_correo": "📧 Gracias. Ahora escribe tu *correo electrónico*.",
            "form_tc": (
                "📄 *Términos y condiciones*\n"
                "1) Contrato de servicios educativos.\n"
                "2) Política de datos personales.\n\n"
                "¿Aceptas los términos? Responde *sí* o *no*."
            ),
            "form_otp_enviado": (
                "✅ Perfecto. Te enviamos un *código de verificación* por WhatsApp.\n"
                "Escribe el código (6 dígitos) para confirmar tu matrícula."
            ),
            "form_otp_invalido": "❌ Código incorrecto. Intenta de nuevo.",
            "form_otp_max": "⛔ Has superado el número de intentos. Escribe *matricularme* para reiniciar el proceso.",
            "matricula_ok": (
                "🎉 *¡Matrícula completada!*\n"
                "Registramos tus datos y te contactaremos para agendar.\n"
                "Gracias por confiar en nosotros 🚗"
            ),
            "matricula_cancelada": "❌ Proceso cancelado. Escribe *matricularme* para iniciar de nuevo."
        }

        self.syn = {
            "inicio": {
                "1": "menu_nuevo_estudiante",
                "nuevo": "menu_nuevo_estudiante",
                "matricularme": "inicio_matricula",
                "2": "menu_estudiante_activo",
                "activo": "menu_estudiante_activo",
            },
            "menu_nuevo_estudiante": {
                "1": "menu_cursos",
                "cursos": "menu_cursos",
                "2": "inicio_matricula",
                "matricularme": "inicio_matricula",
                "3": "inicio",
                "volver": "inicio"
            },
            "menu_estudiante_activo": {
                "1": "agendar_practica",
                "agendar": "agendar_practica",
                "practica": "agendar_practica",
                "2": "programar_examen",
                "examen": "programar_examen",
                "3": "solicitar_certificacion",
                "certificacion": "solicitar_certificacion",
                "4": "menu_cursos",
                "5": "inicio",
                "volver": "inicio"
            },
            "menu_cursos": {
                "a": "curso_carro",
                "carro": "curso_carro",
                "b": "curso_moto",
                "moto": "curso_moto",
                "c": "curso_reentrenamiento",
                "reentrenamiento": "curso_reentrenamiento",
                "volver": "inicio"
            },
            "curso_carro": {"matricularme": "inicio_matricula", "volver": "menu_cursos"},
            "curso_moto": {"matricularme": "inicio_matricula", "volver": "menu_cursos"},
            "curso_reentrenamiento": {"matricularme": "inicio_matricula", "volver": "menu_cursos"},
            "agendar_practica": {"*": "confirmar_practica"},
            "programar_examen": {"*": "confirmar_examen"},
            "solicitar_certificacion": {"*": "inicio"},
            "inicio_matricula": {"*": "matricula_nombre"},
            "matricula_nombre": {"*": "matricula_correo"},
            "matricula_correo": {"sí": "matricula_aceptado", "si": "matricula_aceptado", "no": "matricula_cancelado"},
            "matricula_aceptado": {"*": "matricula_otp"},
            "matricula_otp": {"*": "matricula_confirmar"},
            "matricula_confirmar": {"*": "inicio"},
        }

    # ---------- utilidades ----------
    def set_user(self, wa_from: str):
        """Guarda el identificador del usuario (ej. 'whatsapp:+57...')."""
        self.session["wa_from"] = wa_from

    def _norm(self, text: str) -> str:
        if text is None: return ""
        t = text.strip().lower()
        t = (t.replace("á","a").replace("é","e")
               .replace("í","i").replace("ó","o")
               .replace("ú","u").replace("ü","u"))
        t = re.sub(r"\s+", " ", t)
        return t

    def _global_cmd(self, entrada):
        e = self._norm(entrada)
        if e in {"ayuda","help","?","info"}: return "ayuda"
        if e in {"menu","inicio","start","hola","hi"}: return "inicio"
        if e in {"volver","atras","atrás","back"}: return "inicio"
        return None

    def _msg(self, key): return self.mensajes.get(key, "…")
    def _valid_email(self, email): return bool(self.EMAIL_RE.match(email or ""))
    def _gen_otp(self): return f"{random.randint(100000, 999999)}"

    # ---------- API principal ----------
    def procesar_opcion(self, estado_actual, entrada_usuario):
        atajo = self._global_cmd(entrada_usuario)
        if atajo:
            return (self._msg(atajo) if atajo == "ayuda" else self._msg("inicio"),
                    atajo if atajo != "ayuda" else estado_actual)

        estado = estado_actual if estado_actual in self.syn else "inicio"
        entrada = self._norm(entrada_usuario)

        trans = self.syn.get(estado, {})
        if "*" in trans:
            prox = trans["*"]
        else:
            # equivalencias
            eq = {
                "1":"1","uno":"1",
                "2":"2","dos":"2",
                "3":"3","tres":"3",
                "4":"4","cuatro":"4",
                "5":"5","cinco":"5",
                "a":"a","b":"b","c":"c"
            }
            entrada_eq = eq.get(entrada, entrada)
            prox = trans.get(entrada_eq)

        if prox is None:
            return (f"⚠️ Opción no válida.\n\n{self._fallback_mensaje(estado)}", estado)

        return self._on_state(prox, entrada)

    def _fallback_mensaje(self, estado):
        mapping = {
            "inicio": self._msg("inicio"),
            "menu_nuevo_estudiante": self._msg("menu_nuevo_estudiante"),
            "menu_estudiante_activo": self._msg("menu_estudiante_activo"),
            "menu_cursos": self._msg("menu_cursos"),
            "curso_carro": self._msg("curso_carro"),
            "curso_moto": self._msg("curso_moto"),
            "curso_reentrenamiento": self._msg("curso_reentrenamiento"),
            "agendar_practica": "🕒 Indica día y hora. Ej: *Lunes 3 PM*",
            "programar_examen": "🧠 Escribe la fecha del examen. Ej: *2025-10-30*",
            "solicitar_certificacion": "📜 Escribe tu número de documento.",
            "inicio_matricula": self._msg("form_nombre"),
            "matricula_nombre": self._msg("form_correo"),
            "matricula_correo": self._msg("form_tc"),
            "matricula_aceptado": self._msg("form_otp_enviado"),
            "matricula_otp": "🔐 Escribe el código de 6 dígitos.",
        }
        return mapping.get(estado, self._msg("inicio"))

    # ---------- handlers por estado ----------
    def _on_state(self, estado, entrada):
        if estado == "inicio": return self._msg("inicio"), "inicio"
        if estado == "menu_nuevo_estudiante": return self._msg("menu_nuevo_estudiante"), estado
        if estado == "menu_estudiante_activo": return self._msg("menu_estudiante_activo"), estado
        if estado == "menu_cursos": return self._msg("menu_cursos"), estado

        if estado in {"curso_carro","curso_moto","curso_reentrenamiento"}:
            self.session["ultimo_curso"] = estado
            return self._msg(estado), estado

        if estado == "agendar_practica":
            return "🕒 Indica día y hora. Ej: *Lunes 3 PM*", "agendar_practica"
        if estado == "confirmar_practica":
            return "✅ Clase práctica agendada. Te enviaremos confirmación por correo.", "inicio"
        if estado == "programar_examen":
            return "🧠 Escribe la fecha del examen. Ej: *2025-10-30*", "programar_examen"
        if estado == "confirmar_examen":
            return "✅ Examen teórico programado correctamente. ¡Éxitos!", "inicio"
        if estado == "solicitar_certificacion":
            return "📜 Escribe tu número de documento. Te avisaremos cuando esté lista.", "solicitar_certificacion"

        if estado == "inicio_matricula":
            self.session["matricula"] = {"nombre": None, "correo": None, "tc_aceptados": False, "otp": None, "otp_intentos": 0}
            return self._msg("form_nombre"), "inicio_matricula"

        if estado == "matricula_nombre":
            nombre = entrada.strip().title()
            if len(nombre.split()) < 2:
                return "⚠️ Por favor, ingresa tu *nombre y apellido*.", "inicio_matricula"
            self.session["matricula"]["nombre"] = nombre
            return self._msg("form_correo"), "matricula_nombre"

        if estado == "matricula_correo":
            if not self._valid_email(entrada):
                return "⚠️ El correo no es válido. Intenta de nuevo (ej: nombre@dominio.com).", "matricula_nombre"
            self.session["matricula"]["correo"] = entrada
            return self._msg("form_tc"), "matricula_correo"

        if estado == "matricula_aceptado":
            self.session["matricula"]["tc_aceptados"] = True
            otp = self._gen_otp()
            self.session["matricula"]["otp"] = otp
            # Enviar OTP real si hay callback y número válido
            if callable(self.send_otp_callback) and self.session.get("wa_from"):
                body = f"Tu código de verificación es: {otp}"
                self.send_otp_callback(self.session["wa_from"], body)
            return self._msg("form_otp_enviado"), "matricula_aceptado"

        if estado == "matricula_otp":
            code = re.sub(r"\D", "", entrada)
            if len(code) != 6:
                return "🔐 Ingresa un código de *6 dígitos*.", "matricula_aceptado"
            self.session["matricula"]["otp_intentos"] += 1
            if self.session["matricula"]["otp_intentos"] > 5:
                return self._msg("form_otp_max"), "inicio"
            if code != self.session["matricula"]["otp"]:
                return self._msg("form_otp_invalido"), "matricula_aceptado"
            self._guardar_matricula()
            return self._msg("matricula_ok"), "matricula_confirmar"

        if estado == "matricula_confirmar":
            return self._msg("inicio"), "inicio"

        if estado == "matricula_cancelado":
            return self._msg("matricula_cancelada"), "inicio"

        return self._msg("inicio"), "inicio"

    # ---------- persistencia (placeholder) ----------
    def _guardar_matricula(self):
        datos = self.session["matricula"].copy()
        datos.pop("otp", None)
        datos.pop("otp_intentos", None)
        datos["fecha_registro"] = datetime.utcnow().isoformat()
        # TODO: inserta en tu BD
        return True
