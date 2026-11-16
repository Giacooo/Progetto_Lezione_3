// COSA FA QUESTO FILE (lezione 6, step 8)
// Collega la pagina (index.html), lo stato in memoria e le chiamate al back-end (api.js).
//   - elenco delle chat a sinistra: titolo e data dell'ultimo messaggio; "Nuova chat";
//   - chat aperta a destra: messaggi in ordine, strumenti usati sotto le risposte, "Elimina";
//   - invio di una domanda con stato di attesa PER CHAT: mentre una chat aspetta la risposta
//     si possono aprire le altre; la sua casella, "Invia" ed "Elimina" restano disattivati;
//   - errori in un riquadro, con il testo del back-end; se l'invio fallisce la domanda torna
//     nella casella, perché il back-end non l'ha salvata.
// Il testo che arriva dal back-end si inserisce solo con textContent: anche una risposta che
// contiene "<script>" viene mostrata come testo, mai eseguita.

import { creaChat, elencaChat, eliminaChat, inviaMessaggio, leggiChat } from "./api.js";
import { dataElenco, descriviStrumenti, domandaValida, formattaData, titoloChat } from "./logica.js";

const $ = (id) => document.getElementById(id);

const stato = {
  elenco: [], // voci di GET /chat
  aperta: null, // id della chat aperta
  dati: null, // GET /chat/{id} della chat aperta (null mentre si carica)
  attese: new Map(), // id chat → domanda in attesa di risposta
  bozze: new Map(), // id chat → testo nella casella (anche la domanda restituita dopo un errore)
  errori: new Map(), // id chat → messaggio d'errore da mostrare in quella chat
};

// ---------------- Riquadri d'errore ----------------

function mostraErroreElenco(messaggio, conRiprova = false) {
  const riquadro = $("errore-elenco");
  riquadro.querySelector(".testo-errore").textContent = messaggio;
  riquadro.querySelector(".riprova").hidden = !conRiprova;
  riquadro.hidden = false;
}

function nascondiErroreElenco() {
  $("errore-elenco").hidden = true;
}

// ---------------- Disegno ----------------

function disegnaElenco() {
  const ul = $("elenco");
  ul.replaceChildren();
  for (const voce of stato.elenco) {
    const pulsante = document.createElement("button");
    pulsante.type = "button";
    pulsante.setAttribute("aria-current", String(voce.id === stato.aperta));
    const titolo = document.createElement("span");
    titolo.className = "titolo";
    titolo.textContent = voce.titolo;
    const data = document.createElement("span");
    data.className = "data";
    data.textContent = stato.attese.has(voce.id) ? "in attesa di risposta…" : dataElenco(voce);
    pulsante.append(titolo, data);
    pulsante.addEventListener("click", () => apriChat(voce.id));
    const li = document.createElement("li");
    li.append(pulsante);
    ul.append(li);
  }
  const vuoto = $("vuoto");
  if (stato.aperta === null) {
    vuoto.textContent = stato.elenco.length === 0
      ? 'Nessuna chat: premi "Nuova chat" per cominciare.'
      : "Scegli una chat dall'elenco.";
  }
  vuoto.hidden = stato.aperta !== null;
  $("chat-aperta").hidden = stato.aperta === null;
}

function bolla(ruolo, testo, data, strumenti, inAttesa = false) {
  const div = document.createElement("div");
  div.className = `messaggio ${ruolo}` + (inAttesa ? " in-attesa" : "");
  const chi = document.createElement("div");
  chi.className = "chi";
  chi.textContent = (ruolo === "utente" ? "Tu" : "Assistente") + (data ? ` · ${formattaData(data)}` : "");
  const corpo = document.createElement("div");
  corpo.className = "testo";
  corpo.textContent = testo;
  div.append(chi, corpo);
  const riga = descriviStrumenti(strumenti);
  if (riga) {
    const s = document.createElement("div");
    s.className = "strumenti";
    s.textContent = riga;
    div.append(s);
  }
  return div;
}

function disegnaChat() {
  const id = stato.aperta;
  if (id === null) {
    return;
  }
  const inAttesa = stato.attese.has(id);
  $("titolo-chat").textContent = titoloChat(stato.dati, voceAperta());
  $("elimina").disabled = inAttesa;

  const contenitore = $("messaggi");
  contenitore.replaceChildren();
  if (stato.dati === null) {
    const p = document.createElement("p");
    p.className = "attesa";
    p.textContent = "Caricamento della chat…";
    contenitore.append(p);
  } else if (stato.dati.messaggi === null) {
    // La chat non si è potuta leggere (l'errore è nel riquadro): non è vuota, non si sa.
    const p = document.createElement("p");
    p.className = "vuoto";
    p.textContent = "Messaggi non disponibili: riaprire la chat più tardi.";
    contenitore.append(p);
  } else {
    for (const m of stato.dati.messaggi) {
      contenitore.append(bolla(m.ruolo, m.testo, m.data, m.strumenti_usati));
    }
    if (stato.dati.messaggi.length === 0 && !inAttesa) {
      const p = document.createElement("p");
      p.className = "vuoto";
      p.textContent = "Nessun messaggio: scrivi una domanda qui sotto.";
      contenitore.append(p);
    }
  }
  if (inAttesa) {
    contenitore.append(bolla("utente", stato.attese.get(id), null, [], true));
    const p = document.createElement("p");
    p.className = "attesa";
    p.textContent = "L'assistente sta rispondendo…";
    contenitore.append(p);
  }
  contenitore.scrollTop = contenitore.scrollHeight;

  const riquadro = $("errore-chat");
  const errore = stato.errori.get(id);
  riquadro.querySelector(".testo-errore").textContent = errore || "";
  riquadro.hidden = !errore;

  $("domanda").disabled = inAttesa;
  aggiornaInvia();
}

function voceAperta() {
  return stato.elenco.find((v) => v.id === stato.aperta);
}

function aggiornaInvia() {
  const id = stato.aperta;
  $("invia").disabled = id === null || stato.attese.has(id) || !domandaValida($("domanda").value);
}

// ---------------- Azioni ----------------

async function caricaElenco() {
  try {
    stato.elenco = await elencaChat();
    nascondiErroreElenco();
    return true;
  } catch (e) {
    mostraErroreElenco(e.message, true);
    return false;
  } finally {
    disegnaElenco();
  }
}

// La casella appartiene alla chat aperta: cambiando chat si mette da parte il testo scritto.
function conservaBozza() {
  if (stato.aperta !== null && !stato.attese.has(stato.aperta)) {
    stato.bozze.set(stato.aperta, $("domanda").value);
  }
}

async function apriChat(id) {
  conservaBozza();
  stato.aperta = id;
  stato.dati = null;
  $("domanda").value = stato.bozze.get(id) || "";
  disegnaElenco();
  disegnaChat();
  try {
    const dati = await leggiChat(id);
    if (stato.aperta === id) {
      stato.dati = dati;
    }
  } catch (e) {
    if (stato.aperta === id) {
      stato.dati = { titolo: "", messaggi: null }; // messaggi null = non caricati
      stato.errori.set(id, e.message);
    }
    if (e.codice === 404) {
      await chatSparita(id, e.message);
      return;
    }
  }
  if (stato.aperta === id) {
    disegnaChat();
  }
}

// La chat non esiste più (eliminata da un'altra scheda): si chiude e si ricarica l'elenco.
async function chatSparita(id, messaggio) {
  stato.attese.delete(id);
  stato.bozze.delete(id);
  stato.errori.delete(id);
  if (stato.aperta === id) {
    stato.aperta = null;
    stato.dati = null;
  }
  await caricaElenco();
  mostraErroreElenco(messaggio);
}

async function nuovaChat() {
  const pulsante = $("nuova-chat");
  pulsante.disabled = true;
  try {
    const chat = await creaChat();
    await caricaElenco();
    await apriChat(chat.id);
    $("domanda").focus();
  } catch (e) {
    mostraErroreElenco(e.message);
  } finally {
    pulsante.disabled = false;
  }
}

async function eliminaAperta() {
  const id = stato.aperta;
  if (id === null || stato.attese.has(id)) {
    return;
  }
  const titolo = titoloChat(stato.dati, voceAperta());
  if (!confirm(`Eliminare la chat "${titolo}" e tutti i suoi messaggi?`)) {
    return;
  }
  $("elimina").disabled = true;
  try {
    await eliminaChat(id);
  } catch (e) {
    if (e.codice !== 404) {
      stato.errori.set(id, e.message);
      disegnaChat();
      return;
    }
  }
  stato.bozze.delete(id);
  stato.errori.delete(id);
  stato.aperta = null;
  stato.dati = null;
  if ((await caricaElenco()) && stato.elenco.length > 0) {
    await apriChat(stato.elenco[0].id);
  }
}

async function invia() {
  const id = stato.aperta;
  const testo = $("domanda").value;
  if (id === null || stato.attese.has(id) || !domandaValida(testo)) {
    return;
  }
  // Prima di qualunque attesa: così un doppio clic non manda la domanda due volte.
  stato.attese.set(id, testo);
  stato.bozze.delete(id);
  stato.errori.delete(id);
  $("domanda").value = "";
  disegnaElenco();
  disegnaChat();

  try {
    await inviaMessaggio(id, testo);
    stato.attese.delete(id);
    if (stato.aperta === id) {
      try {
        const dati = await leggiChat(id);
        // Di nuovo il controllo DOPO l'attesa: nel frattempo si può essere passati a un'altra
        // chat, e i suoi dati non vanno sostituiti con quelli di questa.
        if (stato.aperta === id) {
          stato.dati = dati;
        }
      } catch (e) {
        stato.errori.set(id, e.message);
      }
    }
  } catch (e) {
    stato.attese.delete(id);
    if (e.codice === 404) {
      await chatSparita(id, e.message);
      return;
    }
    // Il back-end non ha salvato la domanda: torna nella casella, pronta da rimandare.
    stato.bozze.set(id, testo);
    stato.errori.set(id, e.message);
    if (stato.aperta === id) {
      $("domanda").value = testo;
    }
  }
  await caricaElenco();
  if (stato.aperta === id) {
    disegnaChat();
    $("domanda").focus();
  }
}

// ---------------- Avvio ----------------

function collega() {
  $("nuova-chat").addEventListener("click", nuovaChat);
  $("elimina").addEventListener("click", eliminaAperta);
  $("modulo").addEventListener("submit", (evento) => {
    evento.preventDefault();
    invia();
  });
  $("domanda").addEventListener("input", aggiornaInvia);
  $("domanda").addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey && !evento.isComposing) {
      evento.preventDefault();
      invia();
    }
  });
  $("errore-chat").querySelector(".chiudi").addEventListener("click", () => {
    stato.errori.delete(stato.aperta);
    $("errore-chat").hidden = true;
  });
  $("errore-elenco").querySelector(".chiudi").addEventListener("click", nascondiErroreElenco);
  $("errore-elenco").querySelector(".riprova").addEventListener("click", avvia);
}

async function avvia() {
  if ((await caricaElenco()) && stato.aperta === null && stato.elenco.length > 0) {
    await apriChat(stato.elenco[0].id);
  }
}

collega();
avvia();
