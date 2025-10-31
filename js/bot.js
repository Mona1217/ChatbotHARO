// js/bot.js
import {
  API_BASE_URL, ROUTES,
  extractTokens, setTokens, authHeaders, formatPasswordForApi
} from "./config.js";

/* ============ UI helpers ============ */
const ui = {
  chat:  document.getElementById("chat"),
  quick: document.getElementById("quickReplies"),
  input: document.getElementById("userInput"),
  send:  document.getElementById("sendBtn"),
};

function bubble(text, who = "bot"){
  const wrap = document.createElement("div");
  wrap.className = `msg ${who}`;
  wrap.innerHTML = `<div class="bubble"><pre>${text}</pre></div>`;
  ui.chat.appendChild(wrap);
  ui.chat.scrollTop = ui.chat.scrollHeight;
}
function chips(list){
  ui.quick.innerHTML = "";
  (list || []).forEach(o => {
    const b = document.createElement("button");
    b.className = "chip";
    b.textContent = o.label;
    b.onclick = o.onClick;
    ui.quick.appendChild(b);
  });
}
function resetChips(){ ui.quick.innerHTML = ""; }

/* ============ Estado ============ */
const state = {
  step: "inicio",
  consent: false,
  nextAfterOtp: null, // 'registro' | 'consulta'

  // login
  login: { login: "", password: "" },

  // OTP
  otp: { email: "", code: "" },

  // registro prospecto
  reg: {
    nombre: "", apellido: "", tipoDocumento: "", numeroDocumento: "",
    categoria: "", telefono: "", email: "", direccion: "",
    usuario: "", contrasena: ""
  }
};

/* ============ API ============ */
async function apiLogin(login, rawPassword){
  const passwordToSend = await formatPasswordForApi(rawPassword);

  const resp = await fetch(API_BASE_URL + ROUTES.login(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ login, password: passwordToSend })
  });

  const txt = await resp.text();
  let body = {};
  try { body = txt ? JSON.parse(txt) : {}; } catch { body = { raw: txt }; }

  if (!resp.ok) {
    const msg = body?.message || body?.error || `HTTP ${resp.status}`;
    throw new Error(msg);
  }

  const { access, refresh } = extractTokens(resp, body);
  if (!access && !refresh) throw new Error("Inicio de sesión OK pero no llegó token.");
  setTokens({ access, refresh }, login, {
    accesoExpiraEnSeg: body?.accesoExpiraEnSeg,
    refrescoExpiraEnSeg: body?.refrescoExpiraEnSeg
  });

  return body;
}

async function getEstudiantePorDocumento(doc){
  const resp = await fetch(API_BASE_URL + ROUTES.estudianteByDocumento(doc), {
    headers: authHeaders(false),
    credentials: "include"
  });
  if (resp.status === 404 || resp.status === 204) return null;
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return await resp.json();
}

async function crearProspecto(payload){
  // tipoEstudiante se fuerza a 'prospecto' en el back si no viene; aquí lo ponemos explícito
  const body = { ...payload, tipoEstudiante: "prospecto" };

  const resp = await fetch(API_BASE_URL + ROUTES.estudiantesCreate(), {
    method: "POST",
    headers: authHeaders(true),
    credentials: "include",
    body: JSON.stringify(body)
  });

  const txt = await resp.text();
  let data; try { data = txt ? JSON.parse(txt) : {}; } catch { data = { raw: txt }; }
  if (!resp.ok) {
    const msg = data?.message || data?.error || `HTTP ${resp.status}`;
    throw new Error(msg);
  }
  return data;
}

/* ==== OTP según tu Swagger ==== */
// /api/verification/email/send -> body: "user@example.com" (JSON string)
async function sendOtpEmail(email){
  const resp = await fetch(API_BASE_URL + ROUTES.verificationSend(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(email) // << JSON string
  });
  if (!resp.ok) {
    const t = await resp.text();
    let b = {};
    try { b = t ? JSON.parse(t) : {}; } catch { b = { raw: t }; }
    throw new Error(b?.message || b?.error || `HTTP ${resp.status}`);
  }
  return true;
}
// /api/verification/email/verify -> body: { "email": "...", "code": "..." }
async function verifyOtpEmail(email, code){
  const resp = await fetch(API_BASE_URL + ROUTES.verificationVerify(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, code })
  });
  if (!resp.ok) {
    const t = await resp.text();
    let b = {};
    try { b = t ? JSON.parse(t) : {}; } catch { b = { raw: t }; }
    throw new Error(b?.message || b?.error || `HTTP ${resp.status}`);
  }
  return true;
}

/* ============ Textos ============ */
const TRATAMIENTO_DATOS =
`Autorización para tratamiento de datos personales:
CEA HARO tratará tus datos conforme a la Ley 1581 de 2012 con la finalidad de gestionar tu proceso académico y administrativo. ¿Autorizas?`;

/* ============ Menú raíz ============ */
function menuInicio(){
  bubble(
`👋 *Academia de Conducción HARO*

Elige una opción:
1) 🆕 Soy nuevo(a)
2) 🎓 Ya soy estudiante
3) 📝 Registrarme (prospecto)
4) 🔐 Iniciar sesión`
  );
  chips([
    { label: "🆕 Soy nuevo(a)", onClick: flujoNuevo },
    { label: "🎓 Ya soy estudiante", onClick: flujoEstudiante },
    { label: "📝 Registrarme (prospecto)", onClick: flujoRegistroInicio },
    { label: "🔐 Iniciar sesión", onClick: flujoLoginInicio },
  ]);
}

function start(){
  ui.chat.innerHTML = "";
  bubble("👋 Hola, soy el asistente de CEA HARO.");
  bubble("¿En qué puedo ayudarte hoy?");
  state.step = "inicio";
  menuInicio();
}

/* ============ Flujos ============ */
function flujoNuevo(){
  resetChips();
  bubble("🆕 *Nuevo(a)*");
  bubble(TRATAMIENTO_DATOS);
  chips([
    { label: "✅ Sí, autorizo", onClick: ()=>{
      state.consent = true;
      state.nextAfterOtp = "registro";
      resetChips();
      pedirCorreoParaOtp();
    }},
    { label: "❌ No autorizo", onClick: ()=>{
      state.consent = false;
      resetChips();
      start();
    }},
  ]);
}

function flujoEstudiante(){
  resetChips();
  bubble("Antes de continuar…");
  bubble(TRATAMIENTO_DATOS);
  chips([
    { label: "✅ Sí, autorizo", onClick: ()=>{
      state.consent = true;
      state.nextAfterOtp = "consulta";
      resetChips();
      pedirCorreoParaOtp();
    }},
    { label: "❌ No autorizo", onClick: ()=>{
      state.consent = false;
      resetChips();
      start();
    }},
  ]);
}

function flujoLoginInicio(){
  resetChips();
  bubble("🔐 *Iniciar sesión*\nEscribe tu *usuario*.\n\nEjemplo: ayuda69");
  state.login = { login: "", password: "" };
  state.step = "login_user";
  chips([{ label: "⬅️ Volver", onClick: start }]);
}

function flujoRegistroInicio(){
  resetChips();
  Object.keys(state.reg).forEach(k => state.reg[k] = "");
  bubble(
`📝 *Registro de matrícula (prospecto)*
Te pediré 10 datos (con ejemplo):

1) nombre (ej.: Carlos)
2) apellido (ej.: Pérez)
3) tipoDocumento (ej.: CC | TI | CE | Pasaporte)
4) numeroDocumento (ej.: 1029384756)
5) categoria (ej.: A2 | B1 | C1)
6) telefono (ej.: 3005558899)
7) email (ej.: carlos.perez@ceaharo.edu.co)
8) direccion (ej.: Cra 45 #12-34, Bogotá)
9) usuario (ej.: carlos.perez)
10) contrasena (ej.: Clave*2025)

*Nota:* se enviará tipoEstudiante='prospecto' automáticamente.`
  );
  bubble("➡️ 1/10) Escribe tu *nombre* (ej.: Carlos)");
  state.step = "reg_nombre";
  chips([{ label: "⬅️ Volver", onClick: start }]);
}

/* ============ OTP Flow ============ */
function pedirCorreoParaOtp(){
  bubble("📧 Escribe tu *correo* para validar tu identidad.\n\nEjemplo: nombre@dominio.com");
  state.otp = { email: "", code: "" };
  state.step = "otp_email";
  chips([{ label: "⬅️ Volver", onClick: start }]);
}

async function enviarOtp(email){
  bubble("✉️ Enviando código a tu correo…");
  try {
    await sendOtpEmail(email);
    bubble("✅ Código enviado. Escribe el *código de 6 dígitos*.\n\nEjemplo: 123456\n\nSi no te llega, escribe *reenviar*.");
    state.step = "otp_code";
  } catch (e) {
    bubble(`❌ No se pudo enviar el código: ${e.message || ""}`);
    chips([{ label: "⬅️ Volver", onClick: start }]);
    state.step = "inicio";
  }
}

async function verificarOtp(email, code){
  bubble("🔐 Verificando código…");
  try {
    await verifyOtpEmail(email, code);
    bubble("✅ Verificación correcta.");
    if (state.nextAfterOtp === "registro") {
      flujoRegistroInicio();
    } else if (state.nextAfterOtp === "consulta") {
      bubble("✍️ Escribe tu número de cédula para verificar tu registro.\n\n🧾 *Ejemplo*: 1029384756");
      state.step = "consulta_doc";
      chips([{ label: "⬅️ Volver", onClick: start }]);
    } else {
      start();
    }
  } catch (e) {
    bubble(`❌ Código inválido o expirado: ${e.message || ""}\nVuelve a escribir el código o escribe *reenviar* para enviar uno nuevo.`);
    state.step = "otp_code";
  }
}

/* ============ Vista previa organizada ============ */
function vistaPreviaOrganizada(d){
  return [
    `👤 *Nombre:* ${d.nombre} ${d.apellido}`,
    `🧾 *Documento:* ${d.tipoDocumento} ${d.numeroDocumento}`,
    `🚗 *Categoría:* ${d.categoria}`,
    `📞 *Teléfono:* ${d.telefono}`,
    `✉️ *Email:* ${d.email}`,
    `📍 *Dirección:* ${d.direccion}`,
    `🔑 *Usuario:* ${d.usuario}`,
    `🔒 *Contraseña:* ${d.contrasena ? d.contrasena.replace(/./g, "•") : ""}`,
    `🏷️ *Tipo de estudiante:* prospecto`,
  ].join("\n");
}

/* ============ Entrada libre ============ */
ui.send.onclick = () => { const v = ui.input.value; ui.input.value = ""; handleText(v); };
ui.input.addEventListener("keydown", (e) => { if (e.key === "Enter") ui.send.click(); });

async function handleText(text){
  const clean = (text || "").trim();
  if (!clean) return;
  bubble(clean, "user");

  // OTP: email
  if (state.step === "otp_email"){
    state.otp.email = clean;
    await enviarOtp(state.otp.email);
    return;
  }

  // OTP: code
  if (state.step === "otp_code"){
    if (clean.toLowerCase() === "reenviar"){
      await enviarOtp(state.otp.email);
      return;
    }
    state.otp.code = clean;
    await verificarOtp(state.otp.email, state.otp.code);
    return;
  }

  // Consulta por documento
  if (state.step === "consulta_doc"){
    const doc = clean;
    bubble("Consultando…");
    try{
      const data = await getEstudiantePorDocumento(doc);
      if (data){
        bubble(
`✅ Registro encontrado

👤 *Nombre:* ${data.nombre ?? "N/D"} ${data.apellido ?? ""}
🚗 *Categoría:* ${data.categoria ?? "N/D"}
📊 *Estado:* ${data.estado ?? "N/D"}`
        );
      } else {
        bubble("❌ No encontramos tu registro con esa cédula.\nSi eres nuevo(a), puedes iniciar tu matrícula desde el menú.");
      }
    }catch(e){
      bubble("⚠️ Error consultando la API. Verifica backend y CORS.");
    }
    chips([{ label: "🏠 Menú", onClick: start }]);
    state.step = "inicio";
    return;
  }

  // Login
  if (state.step === "login_user"){
    state.login.login = clean;
    bubble("Ahora escribe tu *contraseña*.\n\nEjemplo: ayuda123");
    state.step = "login_pass";
    return;
  }
  if (state.step === "login_pass"){
    state.login.password = clean;
    bubble("Validando credenciales…");
    try{
      await apiLogin(state.login.login, state.login.password);
      bubble("✅ Sesión iniciada correctamente.");
    }catch(e){
      bubble(`❌ Error de inicio de sesión: ${e.message || "Revise credenciales."}`);
    }
    chips([{ label: "🏠 Menú", onClick: start }]);
    state.step = "inicio";
    return;
  }

  // Registro (prospecto) 10 pasos
  switch(state.step){
    case "reg_nombre":
      state.reg.nombre = clean;
      bubble("2/10) *apellido* (ej.: Pérez)");
      state.step = "reg_apellido"; return;

    case "reg_apellido":
      state.reg.apellido = clean;
      bubble("3/10) *tipoDocumento* (ej.: CC | TI | CE | Pasaporte)");
      state.step = "reg_tipoDocumento"; return;

    case "reg_tipoDocumento":
      state.reg.tipoDocumento = clean;
      bubble("4/10) *numeroDocumento* (ej.: 1029384756)");
      state.step = "reg_numeroDocumento"; return;

    case "reg_numeroDocumento":
      state.reg.numeroDocumento = clean;
      bubble("5/10) *categoria* (ej.: A2 | B1 | C1)");
      state.step = "reg_categoria"; return;

    case "reg_categoria":
      state.reg.categoria = clean;
      bubble("6/10) *telefono* (ej.: 3005558899)");
      state.step = "reg_telefono"; return;

    case "reg_telefono":
      state.reg.telefono = clean.replace(/\D/g, "");
      bubble("7/10) *email* (ej.: carlos.perez@ceaharo.edu.co)");
      state.step = "reg_email"; return;

    case "reg_email":
      state.reg.email = clean;
      bubble("8/10) *direccion* (ej.: Cra 45 #12-34, Bogotá)");
      state.step = "reg_direccion"; return;

    case "reg_direccion":
      state.reg.direccion = clean;
      bubble("9/10) *usuario* (ej.: carlos.perez)");
      state.step = "reg_usuario"; return;

    case "reg_usuario":
      state.reg.usuario = clean;
      bubble("10/10) *contrasena* (ej.: Clave*2025)");
      state.step = "reg_contrasena"; return;

    case "reg_contrasena":
      state.reg.contrasena = clean;
      bubble("📦 Revisa tu información antes de enviar:");
      bubble(vistaPreviaOrganizada(state.reg));
      bubble("Escribe *enviar* para registrar o *cancelar* para abortar.");
      state.step = "reg_confirm"; return;

    case "reg_confirm":
      if (clean.toLowerCase() === "enviar"){
        bubble("Enviando…");
        try{
          await crearProspecto(state.reg);
          bubble("✅ Prospecto registrado correctamente.");
        }catch(e){
          bubble(`❌ Error registrando: ${e.message || ""}`);
        }
      } else {
        bubble("Registro cancelado.");
      }
      chips([{ label: "🏠 Menú", onClick: start }]);
      state.step = "inicio";
      return;
  }

  // Fallback a menú
  chips([{ label: "🏠 Menú", onClick: start }]);
  state.step = "inicio";
}

/* ============ Init ============ */
start();
