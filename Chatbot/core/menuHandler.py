class MenuHandler:
    def __init__(self):
        self.menus = {
            "inicio": {
                "mensaje": (
                    "👋 ¡Hola! Bienvenido a la *Academia de Conducción* 🚗\n\n"
                    "Por favor selecciona una opción:\n"
                    "1️⃣ Soy *nuevo estudiante* (quiero información o matricularme)\n"
                    "2️⃣ Soy *estudiante activo* (ya hago parte de la academia)"
                ),
                "transiciones": {
                    "1": "menu_nuevo_estudiante",
                    "2": "menu_estudiante_activo"
                }
            },

            # --- NUEVO ESTUDIANTE ---
            "menu_nuevo_estudiante": {
                "mensaje": (
                    "🆕 Bienvenido nuevo estudiante.\n\n"
                    "Selecciona una opción:\n"
                    "1️⃣ Ver información de cursos\n"
                    "2️⃣ Iniciar proceso de matrícula\n"
                    "3️⃣ Volver al inicio"
                ),
                "transiciones": {
                    "1": "menu_cursos",
                    "2": "inicio_matricula",
                    "3": "inicio"
                }
            },

            # --- FLUJO DE MATRÍCULA ---
            "inicio_matricula": {
                "mensaje": (
                    "📝 Para iniciar tu matrícula necesitamos tus datos básicos.\n"
                    "Por favor escribe tu *nombre completo*."
                ),
                "transiciones": {"*": "matricula_nombre"}  # * = cualquier entrada
            },

            "matricula_nombre": {
                "mensaje": "📧 Gracias. Ahora escribe tu *correo electrónico*.",
                "transiciones": {"*": "matricula_correo"}
            },

            "matricula_correo": {
                "mensaje": (
                    "📄 A continuación te compartiremos los *términos y condiciones* de la matrícula.\n"
                    "Por favor léelos con atención:\n\n"
                    "1️⃣ Contrato de prestación de servicios educativos.\n"
                    "2️⃣ Política de tratamiento de datos personales.\n\n"
                    "¿Aceptas los términos para continuar? (responde *sí* o *no*)"
                ),
                "transiciones": {"sí": "matricula_aceptado", "no": "matricula_cancelado"}
            },

            "matricula_aceptado": {
                "mensaje": (
                    "✅ Perfecto. Para validar tu identidad, te enviaremos un *código de verificación* por WhatsApp.\n"
                    "Por favor escribe el código que recibiste para confirmar tu matrícula."
                ),
                "transiciones": {"*": "matricula_confirmar"}
            },

            "matricula_confirmar": {
                "mensaje": (
                    "🎉 ¡Matrícula completada exitosamente!\n"
                    "Tus datos han sido registrados. Te contactaremos pronto para agendar tus clases.\n\n"
                    "Gracias por confiar en la Academia de Conducción 🚗."
                ),
                "transiciones": {"*": "inicio"}
            },

            "matricula_cancelado": {
                "mensaje": "❌ Proceso cancelado. Puedes volver a intentarlo escribiendo 'matricularme'.",
                "transiciones": {"*": "inicio"}
            },

            # --- ESTUDIANTE ACTIVO ---
            "menu_estudiante_activo": {
                "mensaje": (
                    "🎓 Estudiante activo, selecciona una opción:\n"
                    "1️⃣ Agendar clase práctica\n"
                    "2️⃣ Programar examen teórico\n"
                    "3️⃣ Solicitar certificación\n"
                    "4️⃣ Información general\n"
                    "5️⃣ Volver al inicio"
                ),
                "transiciones": {
                    "1": "agendar_practica",
                    "2": "programar_examen",
                    "3": "solicitar_certificacion",
                    "4": "menu_cursos",
                    "5": "inicio"
                }
            },

            "agendar_practica": {
                "mensaje": (
                    "🕒 Para agendar una clase práctica, por favor indica el día y hora que prefieres.\n"
                    "Ejemplo: *Lunes 3 PM*"
                ),
                "transiciones": {"*": "confirmar_practica"}
            },

            "confirmar_practica": {
                "mensaje": "✅ Clase práctica agendada. Te enviaremos confirmación por correo.",
                "transiciones": {"*": "inicio"}
            },

            "programar_examen": {
                "mensaje": "🧠 Escribe la fecha en la que deseas presentar el examen teórico.",
                "transiciones": {"*": "confirmar_examen"}
            },

            "confirmar_examen": {
                "mensaje": "✅ Examen teórico programado correctamente. ¡Éxitos!",
                "transiciones": {"*": "inicio"}
            },

            "solicitar_certificacion": {
                "mensaje": (
                    "📜 Para solicitar tu certificación, escribe tu número de documento.\n"
                    "Te confirmaremos cuando esté lista para recoger."
                ),
                "transiciones": {"*": "inicio"}
            },

            "menu_cursos": {
                "mensaje": (
                    "📚 Cursos disponibles:\n"
                    "A. Carro particular 🚗\n"
                    "B. Moto 🏍️\n"
                    "C. Reentrenamiento 🔁\n"
                    "Escribe la letra o 'volver'."
                ),
                "transiciones": {
                    "a": "curso_carro",
                    "b": "curso_moto",
                    "c": "curso_reentrenamiento",
                    "volver": "inicio"
                }
            }
        }

    def procesar_opcion(self, estado_actual, entrada_usuario):
        menu = self.menus.get(estado_actual, {})
        transiciones = menu.get("transiciones", {})

        # Si * está presente, cualquier respuesta es válida
        if "*" in transiciones:
            nuevo_estado = transiciones["*"]
        else:
            nuevo_estado = transiciones.get(entrada_usuario, estado_actual)

        if entrada_usuario not in transiciones and "*" not in transiciones:
            respuesta = f"⚠️ Opción no válida.\n\n{menu.get('mensaje', '')}"
        else:
            respuesta = self.menus[nuevo_estado]["mensaje"]

        return respuesta, nuevo_estado
