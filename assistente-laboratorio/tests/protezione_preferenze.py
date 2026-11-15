"""Copia di sicurezza del file delle preferenze durante le prove reali."""

# COSA FA QUESTO FILE
# Non contiene test: contiene l'aiuto che le prove reali dello step 4 usano per non distruggere
# il file delle preferenze VERO dell'utente (archivio/preferenze.json). Prima della prova se ne
# fa una copia su disco (preferenze.json.bak); alla fine, anche se la prova fallisce, il file
# torna com'era (o sparisce, se prima non c'era) e la copia viene tolta. Se la serie viene
# interrotta a metà, la copia resta su disco e il README spiega come rimetterla a posto.

import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def preferenze_protette(percorso: Path) -> Iterator[Path]:
    copia = percorso.with_name(percorso.name + ".bak")
    if copia.exists():
        # Una serie precedente è stata interrotta: la copia potrebbe essere l'unica versione
        # buona del file, quindi non si tocca niente.
        raise RuntimeError(
            f"trovato {copia}: una prova precedente è stata interrotta; rimettere a posto il file "
            "delle preferenze (vedi README) prima di ripetere le prove reali"
        )
    esisteva = percorso.exists()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    if esisteva:
        shutil.copy2(percorso, copia)
    try:
        yield percorso
    finally:
        if esisteva:
            shutil.copy2(copia, percorso)
            copia.unlink()
        else:
            percorso.unlink(missing_ok=True)
