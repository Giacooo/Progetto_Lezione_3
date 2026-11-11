# PORTONE D'INGRESSO DEL PROGRAMMA
# Quando si scrive "python -m assistente", Python cerca proprio questo file e lo esegue.
# Il suo unico compito è far partire la funzione main() del modulo "terminale".

from assistente.terminale import main

# main() restituisce un numero: 0 = tutto bene, 2 = configurazione non valida.
# SystemExit usa quel numero come "codice di uscita" del programma, così chi lo lancia
# (per esempio PowerShell con $LASTEXITCODE) può capire se è andato tutto bene.
raise SystemExit(main())
