# Assistente del laboratorio

Applicazione da terminale in Python il cui turno di conversazione è un grafo LangGraph
esplicito, collegato a un modello locale servito da LM Studio.

Tutti i comandi si eseguono da PowerShell nella cartella `assistente-laboratorio`.

## Preparazione

Serve Python 3.13.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` contiene le dipendenze dell'applicazione; `requirements-dev.txt` aggiunge
`pytest` per i test.

## Test automatici

Non richiedono LM Studio:

```powershell
python -m pytest
```

## Avvio

```powershell
python -m assistente
```

Al prompt `Tu> ` si scrive la domanda. La sessione si chiude con `esci`, con Ctrl+C o con
la fine dell'input; le righe vuote sono ignorate.
