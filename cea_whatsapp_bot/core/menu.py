# core/menu.py
from typing import Tuple, Dict


class MenuHandler:
    def __init__(self):
        # Definición de menús y estados visibles
        self.menus: Dict[str, Dict] = {
            "inicio": {
                "mensaje":
                    "👋 *Bienvenido a la Academia de Conducción*\n\n"
                    "Elige una opción:\n"
                    "1️⃣ *Soy nuevo* (información / matrícula)\n"
                    "2️⃣ *Soy estudiante activo*",
                "transiciones": {"1": "nuevo", "2": "activo"}
            },

            # ----- NUEVO -----
            "nuevo": {
                "mensaje":
                    "🆕 *Nuevo estudiante*\n"
                    "a) Información de cursos\n"
                    "b) Costos y horarios\n"
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
                    "📚 Ofrecemos: *B1, C1, C2*.\n"
                    "Responde *horarios*, *requisitos* o *volver*.",
                "transiciones": {"volver": "nuevo", "*": "info_cursos"}
            },
            "costos": {
                "mensaje":
                    "💰 Costos aproximados: B1 desde $X, C1 desde $Y.\n"
                    "Para detalle escribe *cotizar* o *volver*.",
                "transiciones": {"cotizar": "cotizar", "volver": "nuevo", "*": "costos"}
            },
            "cotizar": {
                "mensaje":
                    "📄 Envíame: *clase de licencia (B1/C1/C2)* y si necesitas *financiación*.\n"
                    "O *volver*.",
                "transiciones": {"volver": "costos", "*": "cotizar"}
            },
            "matricula": {
                "mensaje":
                    "📝 Para matrícula necesito tu *nombre completo* y *documento*.\n"
                    "O escribe *volver*.",
                "transiciones": {"volver": "nuevo", "*": "matricula"}
            },

            # ----- ACTIVO -----
            "activo": {
                "mensaje":
                    "🎓 *Estudiante activo*\n"
                    "a) Agendar clase práctica\n"
                    "b) Programar examen teórico\n"
                    "c) Certificación y trámites\n"
                    "🔐 Escribe *autenticar* para ver tu información\n"
                    "d) Volver",
                "transiciones": {
                    "a": "agendar_practica",
                    "b": "examen_teorico",
                    "c": "certificados",
                    "d": "inicio",
                    "autenticar": "login_estudiante",
                    "*": "activo"
                }
            },
            "agendar_practica": {
                "mensaje":
                    "🗓️ Para agendar práctica envía: *placa*, *fecha deseada (AAAA-MM-DD)*, *hora*.\n"
                    "O escribe *volver*.",
                "transiciones": {"volver": "activo", "*": "agendar_practica"}
            },
            "examen_teorico": {
                "mensaje":
                    "🧠 Para el examen teórico, opciones: *simulador*, *fecha*, *volver*.",
                "transiciones": {"volver": "activo", "*": "examen_teorico"}
            },
            "certificados": {
                "mensaje":
                    "📄 Certificados y trámites: *estado*, *requisitos*, *volver*.",
                "transiciones": {"volver": "activo", "*": "certificados"}
            },

            # ----- CONSENTIMIENTO + LOGIN -----
            "politica_activo": {
                "mensaje":
                    "🛡️ *Tratamiento de datos*\n"
                    "Usaremos tus datos para matrícula, agendamiento y contacto, conforme a la normatividad vigente.\n"
                    "Si estás de acuerdo, responde: *acepto*\n"
                    "Para más info escribe: *politica*",
                "transiciones": {
                    # el bot maneja 'acepto' y luego envía a login_estudiante
                    "*": "politica_activo"
                }
            },
            "login_estudiante": {
                "mensaje":
                    "🔐 *Verificación de identidad*\n"
                    "Por favor escribe tu número de *cédula* así:\n"
                    "• *1094XXXXXX*  (sin espacios ni puntos).\n"
                    "Escribe *volver* para regresar.",
                "transiciones": {
                    "volver": "activo",
                    "*": "login_estudiante"  # permanece hasta que envíe el doc
                }
            },

            # ----- PSEUDO-ESTADOS (internos) para evitar KeyError -----
            # Se usan cuando el flujo ya no pasa por menú sino por lógica del bot.
            "login_pedir_email": {
                "mensaje": "📧 Por favor escribe tu correo electrónico (ej.: usuario@dominio.com).",
                "transiciones": {
                    "volver": "inicio",
                    "*": "login_pedir_email"
                }
            },
            "verificar_otp_email": {
                "mensaje": "🔐 Ingresa tu código OTP así: *otp 123456*.",
                "transiciones": {
                    "volver": "inicio",
                    "*": "verificar_otp_email"
                }
            },
        }

    def siguiente(self, estado: str, entrada: str) -> Tuple[str, str]:
        """
        Dado un estado actual y una entrada de usuario, retorna (mensaje, nuevo_estado).
        Si el nuevo estado no está definido como menú (p. ej., estados internos de login),
        retorna ("", nuevo_estado) para que la lógica del bot lo maneje.
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

        # Si el nuevo estado no tiene menú (estado interno manejado por el bot), evita KeyError
        if nuevo not in self.menus:
            return ("", nuevo)

        respuesta = self.menus[nuevo]["mensaje"]

        # Mensaje de "opción no válida" solo cuando el estado define transiciones explícitas sin comodín
        if entrada_normalizada not in trans and "*" not in trans:
            respuesta = f"⚠️ Opción no válida.\n\n{respuesta}"

        return respuesta, nuevo
