"""Dati e oggetti finti per i test del RAG (lezione 7, esercizio 1)."""

# COSA C'È IN QUESTO FILE
#   CORPUS_PROVA  un piccolo "libro" con le stesse particolarità del file vero di Gutenberg:
#                 BOM, intestazione, righe RICETTE/APPENDICE, introduzioni di capitolo, un titolo
#                 generale senza ricette (MINESTRE), titoli finti in maiuscolo, un rimando
#                 spezzato a capo ("N." + "137. ..."), ingredienti rientrati, corsivi _così_.
#                 Cinque ricette (1-5) in tre capitoli; la 3 è lunga (più di 1200 caratteri).

import math
import zlib

CORPUS_PROVA = "﻿" +"""The Project Gutenberg eBook of La scienza in cucina e l'arte di mangiar bene

This eBook is for the use of anyone anywhere in the United States and
most other parts of the world at no cost and with almost no restrictions.

*** START OF THE PROJECT GUTENBERG EBOOK LA SCIENZA IN CUCINA ***


PREFAZIONE

La cucina è una bricconcella; spesso e volentieri fa disperare.




RICETTE


BRODI, GELATINA E SUGHI

Il brodo è la base di molte vivande e merita qualche parola prima
delle ricette.

1. Brodo

Lo sa il popolo e il comune che per ottenere il brodo buono bisogna
mettere la carne ad acqua diaccia e far bollire la pentola adagino.

2. Gelatina

La gelatina si fa con zampa di vitello e si chiarifica con la chiara
d'uovo sbattuta.

  Zampa di vitello, una.
  Acqua, litri 2.


MINESTRE

Una volta si diceva che la minestra era la biada dell'uomo; oggi i
medici consigliano di mangiarne poca.


MINESTRE IN BRODO

3. Cappelletti all'uso di Romagna

Sono detti così per la loro forma a cappello. Ecco il modo più semplice
di farli perché riescano più delicati e gentili al palato di ognuno.

  Ricotta, grammi 180.
  Petto di cappone, mezzo.
  Parmigiano grattato, grammi 30.
  Uova, uno intero e un rosso.

Cuocete il petto di cappone nel burro, conditelo con sale e pepe e
tritatelo fine colla lunetta. Aggiungete la ricotta, il parmigiano e
le uova, mescolate bene e fate un impasto sodo che si possa lavorare
colle mani senza che si attacchi.

Chiudete il ripieno nella sfoglia tagliata a dischi e piegate i
cappelletti come si usa in Romagna; poi lasciateli asciugare un poco
sopra un tovagliolo infarinato prima di cuocerli nel brodo di cappone,
che è quello che fa al caso loro meglio di ogni altro.

Se vi piace un sapore più grasso potete legare il ripieno con un poco
di _balsamella_ fatta come quella descritta al N.
137. Mettete il composto in un luogo fresco e lasciatelo riposare
almeno un'ora prima di adoperarlo, così prenderà consistenza.

PASTA FROLLA

La sfoglia per i cappelletti non è una pasta frolla, ma una pasta
all'uovo tirata sottile col matterello; badate che non si secchi
mentre lavorate, coprendola con un canovaccio umido.

  UN AMMIRATORE

Un mangiatore moderato si contenta di un centinaio di cappelletti, ma
ho conosciuto chi ne mangiava quattrocento senza batter ciglio e poi
chiedeva il lesso; e si sa che il Natale in Romagna senza i cappelletti
non si concepisce, tanto sono cari alla gente di quella regione.


FRITTI

Il fritto vuole padella ampia e olio abbondante, e la frittura si
giudica dal colore dorato.

4. Pollo fritto

Tagliate il pollo a pezzi, infarinatelo e friggetelo nell'olio bollente
finché non prende un bel colore dorato.

5. Fritto di cervello

Il cervello si lessa, si taglia a pezzetti e si frigge nell'olio
dopo averlo passato nell'uovo e nel pangrattato.


APPENDICE

CUCINA PER GLI STOMACHI DEBOLI

227. Scaloppine ... p. 228.

  RICETTE

*** END OF THE PROJECT GUTENBERG EBOOK LA SCIENZA IN CUCINA ***
"""

INTRODUZIONE_FRITTI = "Il fritto vuole padella ampia e olio abbondante"


class EmbedderFinto:
    """Embedder deterministico al posto di LM Studio: un "sacco di parole" in pochi numeri.

    Ogni parola (in minuscolo, senza punteggiatura) accende una componente scelta con un hash
    stabile; il vettore è poi normalizzato. Testi con parole in comune risultano vicini, e la
    stessa frase dà sempre lo stesso vettore. `chiamate` registra i testi ricevuti.
    """

    def __init__(self, dimensione: int = 32, modello: str = "finto"):
        self.dimensione = dimensione
        self.modello = modello
        self.chiamate: list[list[str]] = []

    def vettore(self, testo: str) -> list[float]:
        valori = [0.0] * self.dimensione
        for parola in testo.lower().split():
            parola = parola.strip(".,;:!?'\"()«»")
            if parola:
                valori[zlib.crc32(parola.encode("utf-8")) % self.dimensione] += 1.0
        if not any(valori):
            valori[0] = 1.0
        norma = math.sqrt(sum(v * v for v in valori))
        return [v / norma for v in valori]

    def calcola(self, testi: list[str]) -> list[list[float]]:
        self.chiamate.append(list(testi))
        return [self.vettore(t) for t in testi]
