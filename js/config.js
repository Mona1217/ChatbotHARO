// js/config.js
// Ajusta esta URL al host/puerto de tu API Java Spring Boot.
export const API_BASE_URL = "http://localhost:8081"; // ej. http://localhost:8081

export const ROUTES = {
  estudiantesSearch: (cedula) => `/api/estudiantes?cedula=${encodeURIComponent(cedula)}`,
  consentPost: `/api/consentimientos`, // si no existe en tu API, deja sin usar
  preinscripcionPost: `/api/matriculas/preinscripcion`, // opcional
};

// Mensaje de tratamiento de datos (reutilizable)
export const TRATAMIENTO_DATOS = `Autorización para tratamiento de datos personales:
CEA HARO, como responsable del tratamiento, informa que sus datos serán tratados conforme a la Ley 1581 de 2012 y demás normas aplicables, con la finalidad de gestionar su proceso académico y administrativo. Usted puede ejercer sus derechos de conocer, actualizar, rectificar y suprimir sus datos, y revocar esta autorización en cualquier momento por los canales oficiales. ¿Autoriza el tratamiento de sus datos personales?`;
