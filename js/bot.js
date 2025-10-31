// js/bot.js
import { API_BASE_URL, ROUTES, TRATAMIENTO_DATOS } from './config.js';

const state = {
  step: 'inicio',      // inicio | menu | nuevo_menu | consent | pide_cedula | resultado_cedula
  consentGiven: false,
  cedula: '',
};

const ui = {
  chat: document.getElementById('chat'),
  input: document.getElementById('userInput'),
  send: document.getElementById('sendBtn'),
  quick: document.getElementById('quickReplies'),
};

function scrollBottom(){ ui.chat.scrollTop = ui.chat.scrollHeight; }

function bubble(text, who='bot'){
  const wrap = document.createElement('div');
  wrap.className = `msg ${who}`;
  wrap.innerHTML = `<div class="bubble"><pre>${text}</pre></div>`;
  ui.chat.appendChild(wrap);
  scrollBottom();
}

function chips(options){
  ui.quick.innerHTML = '';
  options.forEach(o => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.textContent = o.label;
    b.onclick = () => o.onClick();
    ui.quick.appendChild(b);
  });
}
function resetChips(){ ui.quick.innerHTML = ''; }

function start(){
  bubble('👋 Hola, soy el asistente de CEA HARO.');
  bubble('¿En qué puedo ayudarte hoy?');
  state.step = 'menu';
  chips([
    {label: '🆕 Soy nuevo(a)', onClick: flujoNuevo},
    {label: '🎓 Ya soy estudiante', onClick: flujoEstudiante},
  ]);
}

function flujoNuevo(){
  resetChips();
  bubble('Perfecto. Puedo darte información o ayudarte a matricularte.');
  state.step = 'nuevo_menu';
  chips([
    {label: 'ℹ️ Solicitar información', onClick: ()=>{
      resetChips();
      bubble('Te enviaremos la información de programas, costos y horarios. ¿Deseas continuar por este canal?');
      bubble('También puedes escribir a admisiones@ceaharo.edu.co');
      chips([{label:'⬅️ Volver', onClick: start}]);
    }},
    {label: '📝 Matricularme', onClick: ()=>{
      resetChips();
      state.step = 'consent';
      bubble(TRATAMIENTO_DATOS);
      chips([
        {label:'✅ Sí, autorizo', onClick: ()=>{
          state.consentGiven = true;
          resetChips();
          bubble('¡Gracias! Procesemos tu solicitud de matrícula (prueba local).');
          bubble('En producción, se registrará tu consentimiento y se continuará con el proceso en la API.');
          chips([{label:'⬅️ Volver', onClick: start}]);
        }},
        {label:'❌ No autorizo', onClick: ()=>{
          state.consentGiven = false;
          resetChips();
          bubble('Entendido. Sin autorización, no podremos continuar con la matrícula. ¿Quieres otra cosa?');
          chips([{label:'⬅️ Volver', onClick: start}]);
        }},
      ]);
    }},
  ]);
}

function flujoEstudiante(){
  resetChips();
  state.step = 'consent';
  bubble('Antes de continuar…');
  bubble(TRATAMIENTO_DATOS);
  chips([
    {label:'✅ Sí, autorizo', onClick: ()=>{
      state.consentGiven = true;
      resetChips();
      pedirCedula();
    }},
    {label:'❌ No autorizo', onClick: ()=>{
      state.consentGiven = false;
      resetChips();
      bubble('Entendido. Para consultar tu información, necesitamos tu autorización.');
      chips([{label:'⬅️ Volver', onClick: start}]);
    }},
  ]);
}

function pedirCedula(){
  bubble('Por favor, escribe tu número de cédula para verificar si ya estás matriculado(a).');
  state.step = 'pide_cedula';
  resetChips();
  chips([{label:'⬅️ Volver', onClick: start}]);
}

async function buscarCedula(cedula){
  const url = API_BASE_URL + ROUTES.estudiantesSearch(cedula);
  const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
  if (r.status === 404 || r.status === 204) return null;
  if (!r.ok) throw new Error(`Error API (${r.status})`);
  return await r.json();
}

async function handleText(text){
  const clean = text.trim();
  if (!clean) return;
  bubble(clean, 'user');

  if (state.step === 'pide_cedula'){
    state.cedula = clean;
    bubble('Consultando en el sistema…');
    try{
      const data = await buscarCedula(state.cedula);
      if (data){
        bubble('✅ Tu registro existe en HARO.');
        bubble(`Nombre: ${data.nombre ?? 'N/D'}\nPrograma: ${data.programa ?? 'N/D'}`);
      } else {
        bubble('❌ No encontramos tu registro con esa cédula.');
        bubble('Si eres nuevo(a), puedes iniciar tu matrícula desde el menú principal.');
      }
    }catch(err){
      console.error(err);
      bubble('⚠️ No fue posible consultar la API. Revisa que el backend esté encendido y CORS activo.');
    }
    chips([{label:'⬅️ Volver', onClick: start}]);
    state.step = 'resultado_cedula';
    return;
  }

  bubble('¿Deseas volver al menú principal?');
  chips([{label:'🏠 Menú', onClick: start}]);
}

ui.send.onclick = () => handleText(ui.input.value).then(()=>{ ui.input.value=''; });
ui.input.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ ui.send.click(); }});

// init
start();
