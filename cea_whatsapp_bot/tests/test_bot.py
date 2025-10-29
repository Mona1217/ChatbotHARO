from BotController import BotController

mi_numero = "whatsapp:+573001112233"

# 1. Bot me pide el correo
print(BotController.procesar_mensaje(mi_numero, "hola"))
# -> debería decir: "Dame tu correo registrado..."

# 2. Yo le doy mi correo
print(BotController.procesar_mensaje(mi_numero, "alguien@ejemplo.com"))
# -> aquí EL BOT llama al backend Java,
#    el backend manda el correo real,
#    y la respuesta debería ser "Listo. Envié un código..."

# 3. Yo le mando el código que recibí en el correo
print(BotController.procesar_mensaje(mi_numero, "123456"))
# -> debería decir "Recibí tu código..."
