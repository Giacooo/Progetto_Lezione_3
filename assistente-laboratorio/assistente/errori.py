"""Errori riconoscibili mostrati all'utente."""


class ErroreConfigurazione(Exception):
    """La configurazione manca o non è valida: l'applicazione non può partire."""


class ErroreTurno(Exception):
    """Il turno non si è concluso: la cronologia resta com'era."""
