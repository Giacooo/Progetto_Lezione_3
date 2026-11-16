// COSA FA QUESTO FILE (lezione 6, step 8)
// Funzioni "pure" della pagina: ricevono dati e restituiscono testo, senza toccare la pagina né
// la rete. Per questo si possono provare con Node (tests/js/logica.test.mjs).

// Il testo da mostrare a chi usa la pagina quando una chiamata va male.
//   codice: codice HTTP della risposta, oppure null se la risposta non è proprio arrivata;
//   corpo:  il JSON della risposta (null se non era JSON).
export function testoErrore(codice, corpo) {
  if (codice === null) {
    return "Il front-end non risponde: controllare che sia avviato.";
  }
  // I messaggi del back-end ({"errore": "..."}) sono già in italiano e comprensibili.
  if (corpo && typeof corpo === "object" && typeof corpo.errore === "string" && corpo.errore.trim() !== "") {
    return corpo.errore;
  }
  return `Errore imprevisto (codice ${codice}).`;
}

function dueCifre(n) {
  return String(n).padStart(2, "0");
}

// "2026-11-16T09:02:00Z" → "16/11/2026 09:02" nell'ora locale del PC. Costruita a mano e non
// con toLocaleString, che dà formati diversi da un sistema all'altro.
export function formattaData(iso) {
  const d = new Date(iso);
  return `${dueCifre(d.getDate())}/${dueCifre(d.getMonth() + 1)}/${d.getFullYear()} ` +
    `${dueCifre(d.getHours())}:${dueCifre(d.getMinutes())}`;
}

// La data mostrata nell'elenco delle chat: quella dell'ultimo messaggio.
export function dataElenco(voce) {
  return voce.ultimo_messaggio ? formattaData(voce.ultimo_messaggio) : "nessun messaggio";
}

function valore(v) {
  return typeof v === "string" ? v : JSON.stringify(v);
}

// La riga sotto una risposta: "Strumenti usati: calcola (espressione: 45 / 9)".
// Il risultato dello strumento non si mostra: è già riassunto nella risposta.
export function descriviStrumenti(strumenti) {
  if (!strumenti || strumenti.length === 0) {
    return "";
  }
  const voci = strumenti.map((s) => {
    const argomenti = Object.entries(s.argomenti || {}).map(([k, v]) => `${k}: ${valore(v)}`);
    return argomenti.length ? `${s.nome} (${argomenti.join(", ")})` : s.nome;
  });
  return "Strumenti usati: " + voci.join(", ");
}

// Una domanda vuota o di soli spazi non si manda (il back-end la rifiuterebbe).
export function domandaValida(testo) {
  return testo.trim() !== "";
}
