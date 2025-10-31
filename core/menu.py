# core/menu.py
from typing import Tuple, Dict

class MenuHandler:
    def __init__(self):
        self.menus: Dict[str, Dict] = {
            "inicio": {
                "mensaje":
                    "👋 *Academia de Conducción HARO*\n\n"
                    "Elige una opción (pulsa un botón o escribe el número):\n"
                    "1️⃣ *Soy nuevo* (información / matrícula)\n"
                    "2️⃣ *Soy estudiante activo*",
                "transiciones": {"1": "nuevo", "2": "activo"}
            },

            # ----- NUEVO -----
            "nuevo": {
                "mensaje":
                    "🆕 *Nuevo estudiante*\n"
                    "a) Información de cursos (A2/B1/C1)\n"
                    "b) Costos y horarios (referencial)\n"
                    "c) Matricularme\n"
                    "d) Volver",
                "transiciones": {
                    "a": "info_cursos",
                    "b": "costos",
                    "c": "matricula",
                    "d": "inicio",
                    "*": "nuevo"
                }
            },
            "info_cursos": {
                "mensaje":
                    "📚 *Cursos*: A2 (moto), B1/C1 (carro)\n"
                    "Responde *horarios*, *requisitos* o *volver*.",
                "transiciones": {"volver": "nuevo", "*": "info_cursos"}
            },
            "costos": {
                "mensaje":
                    "💰 *Costos referenciales*: según categoría y examen médico.\n"
                    "Escribe *cotizar* para guiarte con tu caso o *volver*.",
                "transiciones": {"cotizar": "cotizar", "volver": "nuevo", "*": "costos"}
            },
            "cotizar": {
                "mensaje":
                    "📄 Para cotizar, indica:\n"
                    "• *Categoría*: A2/B1/C1\n"
                    "• ¿Requieres financiación? *si/no*\n"
                    "Escribe *volver* para regresar.",
                "transiciones": {"volver": "costos", "*": "cotizar"}
            },
            "matricula": {
                "mensaje":
                    "📝 *Matrícula* — envía:\n"
                    "• *Nombre completo*\n"
                    "• *Documento* (solo números)\n"
                    "Escribe *volver* para regresar.",
                "transiciones": {"volver": "nuevo", "*": "matricula"}
            },

            # ----- ACTIVO -----
            "activo": {
                "mensaje":
                    "🎓 *Estudiante activo*\n"
                    "a) Agendar clase práctica\n"
                    "b) Programar examen teórico\n"
                    "c) Certificación y trámites\n"
                    "🔐 Para ver tu avance, primero *autenticar* (correo + OTP)\n"
                    "d) Volver",
                "transiciones": {
                    "a": "agendar_practica",
                    "b": "examen_teorico",
                    "c": "certificados",
                    "d": "inicio",
                    "autenticar": "login_estudiante",
                    "login": "login_estudiante",
                    "*": "activo"
                }
            },
            "agendar_practica": {
                "mensaje":
                    "🗓️ *Agendar práctica* — formato exacto:\n"
                    "• *placa ABC123*\n"
                    "• *fecha 2025-11-02* (AAAA-MM-DD)\n"
                    "• *hora 09:00* (24h)\n"
                    "Ejemplo: *placa ABC123 fecha 2025-11-02 hora 09:00*\n"
                    "Escribe *volver* para regresar.",
                "transiciones": {"volver": "activo", "*": "agendar_practica"}
            },
            "examen_teorico": {
                "mensaje":
                    "🧠 *Examen teórico*\n"
                    "Opciones: *simulador*, *fecha 2025-11-03*, *volver*.",
                "transiciones": {"volver": "activo", "*": "examen_teorico"}
            },
            "certificados": {
                "mensaje":
                    "📄 *Certificados y trámites*\n"
                    "Opciones: *estado*, *requisitos*, *volver*.",
                "transiciones": {"volver": "activo", "*": "certificados"}
            },

            # ----- CONSENTIMIENTO + LOGIN (correo/OTP) -----
            "politica_activo": {
                "mensaje":
                    "🛡️ *Tratamiento de datos*\n"
                    "Usaremos tus datos para matrícula, agenda y contacto.\n"
                    "Si estás de acuerdo, escribe: *acepto*\n"
                    "Para más info: *politica*",
                "transiciones": {"*": "politica_activo"}
            },
            "login_estudiante": {
                "mensaje":
                    "🔐 *Autenticación por correo + OTP*\n"
                    "1) Escribe *correo* y envía tu email\n"
                    "2) Recibirás un *código OTP*\n"
                    "3) Escríbelo así: *otp 123456*\n"
                    "Escribe *volver* para regresar.",
                "transiciones": {
                    "correo": "login_pedir_email",
                    "volver": "activo",
                    "*": "login_estudiante"
                }
            },

            # ----- PSEUDO-ESTADOS (internos, definidos para evitar KeyError) -----
            "login_pedir_email": {
                "mensaje":
                    "📧 Escribe tu *correo electrónico* (ej.: usuario@dominio.com).\n"
                    "Luego ingresa el *OTP* así: *otp 123456*.",
                "transiciones": {"volver": "inicio", "*": "login_pedir_email"}
            },
            "verificar_otp_email": {
                "mensaje":
                    "🔐 Ingresa tu *código OTP* así: *otp 123456*.\n"
                    "Escribe *volver* para reiniciar.",
                "transiciones": {"volver": "inicio", "*": "verificar_otp_email"}
            },
        }

    def siguiente(self, estado: str, entrada: str) -> Tuple[str, str]:
        """
        Dado estado actual y entrada, retorna (mensaje, nuevo_estado).
        Si 'nuevo' no existe en menús (estado interno), retorna ('', nuevo) para que
        el core lo maneje sin romper.
        """
        estado = (estado or "inicio")
        entrada_normalizada = (entrada or "").strip().lower()

        menu = self.menus.get(estado, self.menus["inicio"])
        trans = menu.get("transiciones", {})

        if entrada_normalizada in trans:
            nuevo = trans[entrada_normalizada]
        elif "*" in trans:
            nuevo = trans["*"]
        else:
            nuevo = estado

        if nuevo not in self.menus:
            return ("", nuevo)

        respuesta = self.menus[nuevo]["mensaje"]

        if entrada_normalizada not in trans and "*" not in trans:
            respuesta = f"⚠️ Opción no válida.\n\n{respuesta}"

        return respuesta, nuevo
