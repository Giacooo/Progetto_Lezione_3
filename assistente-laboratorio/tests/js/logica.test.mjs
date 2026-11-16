// Test delle funzioni pure della pagina (lezione 6, step 8).
//
// COSA PROVA QUESTO FILE
// frontend/statico/logica.js con il test runner integrato in Node (node --test), senza
// pacchetti npm. Lo esegue tests/test_frontend_js.py con TZ=UTC, così le ore sono prevedibili.

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  dataElenco,
  descriviStrumenti,
  domandaValida,
  formattaData,
  testoErrore,
} from "../../frontend/statico/logica.js";

test("testoErrore: nessuna risposta dal front-end", () => {
  assert.equal(testoErrore(null, null), "Il front-end non risponde: controllare che sia avviato.");
});

test("testoErrore: messaggio del back-end così com'è", () => {
  const m = "Agente non raggiungibile: la domanda non è stata salvata, riprovare più tardi.";
  assert.equal(testoErrore(503, { errore: m }), m);
});

test("testoErrore: corpo senza 'errore' o non JSON", () => {
  assert.equal(testoErrore(404, { detail: "Not Found" }), "Errore imprevisto (codice 404).");
  assert.equal(testoErrore(500, null), "Errore imprevisto (codice 500).");
  assert.equal(testoErrore(502, { errore: "  " }), "Errore imprevisto (codice 502).");
  assert.equal(testoErrore(500, "testo"), "Errore imprevisto (codice 500).");
});

test("formattaData: giorno/mese/anno ore:minuti con zeri", () => {
  assert.equal(formattaData("2026-11-16T09:02:00Z"), "16/11/2026 09:02");
  assert.equal(formattaData("2026-01-05T23:59:59.123456+00:00"), "05/01/2026 23:59");
});

test("dataElenco: chat vuota o con messaggi", () => {
  assert.equal(dataElenco({ ultimo_messaggio: null }), "nessun messaggio");
  assert.equal(dataElenco({ ultimo_messaggio: "2026-11-16T09:02:00Z" }), "16/11/2026 09:02");
});

test("descriviStrumenti", () => {
  assert.equal(descriviStrumenti([]), "");
  assert.equal(descriviStrumenti(undefined), "");
  assert.equal(
    descriviStrumenti([{ nome: "calcola", argomenti: { espressione: "45 / 9" } }]),
    "Strumenti usati: calcola (espressione: 45 / 9)",
  );
  assert.equal(
    descriviStrumenti([
      { nome: "ora_corrente", argomenti: {} },
      { nome: "converti_unita", argomenti: { valore: 3, da: "km" } },
    ]),
    "Strumenti usati: ora_corrente, converti_unita (valore: 3, da: km)",
  );
});

test("domandaValida", () => {
  assert.equal(domandaValida("  \n"), false);
  assert.equal(domandaValida(""), false);
  assert.equal(domandaValida(" ciao "), true);
});
