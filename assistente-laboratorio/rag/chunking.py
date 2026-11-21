"""Chunking: divisione del testo di una ricetta in pezzi (lezione 7, pipeline fase 4)."""

# COSA FA QUESTO FILE
# Un chunk è il pezzo di testo che diventa un punto in Qdrant: deve essere abbastanza piccolo
# da parlare di una cosa sola e abbastanza grande da avere senso da solo. Due strategie (PDF,
# pag. 15), scelte con CHUNK_STRATEGIA:
#   - "paragrafi" (la "combinazione frequente"): una ricetta corta resta un solo chunk; una
#     lunga si divide mettendo insieme paragrafi interi finché si sta nella dimensione (un
#     elenco di ingredienti è un paragrafo e non si spezza); un paragrafo da solo troppo lungo
#     si taglia a finestra;
#   - "finestra": pezzi di lunghezza fissa, ognuno che ricomincia un po' prima della fine del
#     precedente.
# In tutte e due, dal secondo chunk in poi si ripete la coda del precedente (CHUNK_OVERLAP
# caratteri al massimo): così una frase a cavallo del taglio si ritrova intera in uno dei due.
# I tagli cadono sempre tra una parola e l'altra: un chunk può superare la dimensione al massimo
# della parola in corso. L'indice nella lista restituita è la "posizione" del chunk (0, 1, 2...).

SEPARATORE = "\n\n"


def _inizio_parola(testo: str, posizione: int) -> int:
    """Sposta `posizione` in avanti fino all'inizio di una parola (o alla fine del testo)."""
    if 0 < posizione < len(testo) and not testo[posizione - 1].isspace():
        while posizione < len(testo) and not testo[posizione].isspace():
            posizione += 1
    while posizione < len(testo) and testo[posizione].isspace():
        posizione += 1
    return posizione


def _coda(testo: str, limite: int) -> str:
    """Gli ultimi `limite` caratteri al massimo del testo, a partire dall'inizio di una parola."""
    if limite <= 0:
        return ""
    if len(testo) <= limite:
        return testo.strip()
    return testo[_inizio_parola(testo, len(testo) - limite):].strip()


def _finestra(testo: str, dimensione: int, overlap: int) -> list[str]:
    pezzi = []
    inizio = _inizio_parola(testo, 0)
    while inizio < len(testo):
        fine = inizio + dimensione
        if fine >= len(testo):
            pezzi.append(testo[inizio:].strip())
            break
        # Non spezzare la parola in corso: il taglio va alla sua fine.
        if not testo[fine - 1].isspace():
            while fine < len(testo) and not testo[fine].isspace():
                fine += 1
        pezzi.append(testo[inizio:fine].strip())
        nuovo = _inizio_parola(testo, fine - overlap)
        # Si va sempre avanti, anche con un overlap quasi uguale alla dimensione.
        inizio = nuovo if nuovo > inizio else _inizio_parola(testo, fine)
    return [p for p in pezzi if p]


def _paragrafi(testo: str, dimensione: int, overlap: int) -> list[str]:
    chunk: list[str] = []
    corrente = ""
    for paragrafo in (p for p in testo.split(SEPARATORE) if p.strip()):
        prova = corrente + SEPARATORE + paragrafo if corrente else paragrafo
        if len(prova) <= dimensione:
            corrente = prova
            continue
        if corrente:
            chunk.append(corrente)
        if len(paragrafo) <= dimensione:
            # Il nuovo chunk comincia con la coda del precedente, accorciata se serve a stare
            # nella dimensione insieme al paragrafo.
            limite = min(overlap, dimensione - len(paragrafo) - len(SEPARATORE))
            coda = _coda(corrente, limite) if corrente else ""
            corrente = coda + SEPARATORE + paragrafo if coda else paragrafo
        else:
            # Paragrafo troppo lungo da solo: si taglia a finestra (con davanti la coda del
            # chunk precedente); l'ultimo pezzo può ancora accogliere i paragrafi successivi.
            coda = _coda(corrente, overlap) if corrente else ""
            pezzi = _finestra(coda + SEPARATORE + paragrafo if coda else paragrafo, dimensione, overlap)
            chunk.extend(pezzi[:-1])
            corrente = pezzi[-1]
    if corrente:
        chunk.append(corrente)
    return chunk


def lunghezza_overlap(precedente: str, chunk: str, overlap: int) -> int:
    """Quanti caratteri all'inizio di `chunk` ripetono la fine di `precedente` (al massimo `overlap`).

    È la parte portata dall'overlap: in tutte e due le strategie il chunk successivo comincia con
    la coda del precedente, mai più lunga di CHUNK_OVERLAP. 0 se non c'è niente in comune.
    """
    for n in range(min(overlap, len(precedente), len(chunk)), 0, -1):
        if precedente.endswith(chunk[:n]):
            return n
    return 0


def dividi(testo: str, strategia: str, dimensione: int, overlap: int) -> list[str]:
    """I chunk del testo di una ricetta, nell'ordine (indice = posizione del chunk)."""
    if strategia not in ("paragrafi", "finestra"):
        raise ValueError(f"strategia di chunking sconosciuta: {strategia!r}")
    testo = testo.strip()
    if len(testo) <= dimensione:
        return [testo] if testo else []
    if strategia == "paragrafi":
        return _paragrafi(testo, dimensione, overlap)
    return _finestra(testo, dimensione, overlap)
