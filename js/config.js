// js/config.js
export const API_BASE_URL = "http://localhost:8081"; // ajusta host/puerto si aplica

export const ROUTES = {
  // Auth
  login:   () => `/api/auth/login`,
  logout:  () => `/api/auth/logout`,
  refresh: () => `/api/auth/refresh`,

  // Estudiantes
  estudiantesCreate:      () => `/api/estudiantes`,
  estudianteByDocumento:  (doc) => `/api/estudiantes/por-documento/${encodeURIComponent(doc)}`,

  // Verificación por correo (OTP)
  verificationSend:   () => `/api/verification/email/send`,
  verificationVerify: () => `/api/verification/email/verify`,
};

export const STORAGE = {
  ACCESS:      "haro.tokenAcceso",
  REFRESH:     "haro.tokenRefresco",
  USER:        "haro.user",
  ACCESS_EXP:  "haro.accesoExpiraEnSeg",
  REFRESH_EXP: "haro.refrescoExpiraEnSeg",
};

export const PASSWORD_MODE = "sha256";

// === Util: SHA-256 a hex (Web Crypto) ===
export async function sha256Hex(text){
  const enc = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest("SHA-256", enc);
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}
export async function formatPasswordForApi(rawPassword){
  return PASSWORD_MODE === "sha256" ? sha256Hex(rawPassword) : rawPassword;
}

// === Tokens ===
export function extractTokens(resp, body){
  // busca primero tokenAcceso/tokenRefresco en body; luego variantes comunes; por último header Authorization
  const lower = (obj) => Object.fromEntries(Object.entries(obj || {}).map(([k,v]) => [String(k).toLowerCase(), v]));
  const b = lower(body || {});
  let access  = b["tokenacceso"]     || b["access_token"]  || b["accesstoken"]  || b["token"] || null;
  let refresh = b["tokenrefresco"]   || b["refresh_token"] || b["refreshtoken"] || null;

  if (!access) {
    const h = resp.headers?.get?.("Authorization") || resp.headers?.get?.("authorization");
    if (h && /^Bearer\s+/i.test(h)) access = h.replace(/^Bearer\s+/i, "").trim();
  }
  return { access, refresh };
}

export function setTokens({ access, refresh }, login, meta = {}){
  if (access)  localStorage.setItem(STORAGE.ACCESS, access);
  if (refresh) localStorage.setItem(STORAGE.REFRESH, refresh);
  if (login)   localStorage.setItem(STORAGE.USER, login);
  if (meta.accesoExpiraEnSeg != null)   localStorage.setItem(STORAGE.ACCESS_EXP,  String(meta.accesoExpiraEnSeg));
  if (meta.refrescoExpiraEnSeg != null) localStorage.setItem(STORAGE.REFRESH_EXP, String(meta.refrescoExpiraEnSeg));
}
export function getAccessToken(){  return localStorage.getItem(STORAGE.ACCESS); }
export function getRefreshToken(){ return localStorage.getItem(STORAGE.REFRESH); }
export function clearTokens(){
  localStorage.removeItem(STORAGE.ACCESS);
  localStorage.removeItem(STORAGE.REFRESH);
  localStorage.removeItem(STORAGE.USER);
  localStorage.removeItem(STORAGE.ACCESS_EXP);
  localStorage.removeItem(STORAGE.REFRESH_EXP);
}
export function authHeaders(json = true){
  const h = {};
  if (json) h["Content-Type"] = "application/json";
  const t = getAccessToken();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}
