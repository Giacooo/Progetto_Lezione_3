// COSA FA QUESTO FILE (lezione 6, step 8)
// Le chiamate al back-end, una funzione per ogni operazione del contratto (il documento OpenAPI
// del back-end, copiato in frontend/contratto/openapi-backend.json). La tabella OPERAZIONI usa
// gli stessi metodi e percorsi del contratto: un test (tests/test_frontend_contratto.py)
// controlla che ogni riga ci sia davvero.
// Le chiamate vanno a /api/...: le riceve il server del front-end, che le inoltra al back-end.
// La pagina non conosce l'indirizzo del back-end (sta nella configurazione del server).

import { testoErrore } from "./logica.js";

export const OPERAZIONI = {
  elencaChat: ["GET", "/chat"],
  creaChat: ["POST", "/chat"],
  leggiChat: ["GET", "/chat/{chat_id}"],
  eliminaChat: ["DELETE", "/chat/{chat_id}"],
  inviaMessaggio: ["POST", "/chat/{chat_id}/messaggi"],
};

// Errore di una chiamata: message è già il testo da mostrare; codice è null se la risposta non
// è arrivata (front-end spento o rete assente).
export class ErroreApi extends Error {
  constructor(messaggio, codice) {
    super(messaggio);
    this.codice = codice;
  }
}

async function chiama(operazione, chatId, corpo) {
  const [metodo, schema] = OPERAZIONI[operazione];
  const percorso = schema.replace("{chat_id}", encodeURIComponent(String(chatId)));
  const opzioni = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    opzioni.headers["Content-Type"] = "application/json";
    opzioni.body = JSON.stringify(corpo);
  }

  let risposta;
  try {
    risposta = await fetch("/api" + percorso, opzioni);
  } catch {
    throw new ErroreApi(testoErrore(null, null), null);
  }
  if (risposta.status === 204) {
    return null;
  }
  let dati = null;
  try {
    dati = await risposta.json();
  } catch {
    dati = null; // risposta non JSON (per esempio una pagina d'errore)
  }
  if (!risposta.ok) {
    throw new ErroreApi(testoErrore(risposta.status, dati), risposta.status);
  }
  return dati;
}

export const elencaChat = () => chiama("elencaChat");
export const creaChat = () => chiama("creaChat", undefined, {});
export const leggiChat = (id) => chiama("leggiChat", id);
export const eliminaChat = (id) => chiama("eliminaChat", id);
export const inviaMessaggio = (id, testo) => chiama("inviaMessaggio", id, { messaggio: testo });
