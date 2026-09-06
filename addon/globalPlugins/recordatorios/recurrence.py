# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Modelo y utilidades para la recurrencia de recordatorios."""

from datetime import timedelta

import addonHandler

addonHandler.initTranslation()


# Claves internas estables (no traducir); se persisten en JSON.
RECURRENCE_DAILY = "daily"
RECURRENCE_WEEKLY = "weekly"
RECURRENCE_MONTHLY = "monthly"
RECURRENCE_CUSTOM = "custom"
RECURRENCE_KEYS = (RECURRENCE_DAILY, RECURRENCE_WEEKLY, RECURRENCE_MONTHLY, RECURRENCE_CUSTOM)


def recurrence_labels():
    """Devuelve las etiquetas traducidas en el mismo orden que `RECURRENCE_KEYS`."""
    return [
        # Translators: Opción de recurrencia diaria.
        _("diario"),
        # Translators: Opción de recurrencia semanal.
        _("semanal"),
        # Translators: Opción de recurrencia mensual.
        _("mensual"),
        # Translators: Opción de recurrencia personalizada (intervalo en minutos).
        _("Personalizado"),
    ]


# Mapa de valores antiguos (texto en español, anterior a la introducción de claves internas)
# a su clave estable. Permite migrar archivos `recordatorios.json` existentes.
_LEGACY_RECURRENCE_MAP = {
    "diario": RECURRENCE_DAILY,
    "semanal": RECURRENCE_WEEKLY,
    "mensual": RECURRENCE_MONTHLY,
    "Personalizado": RECURRENCE_CUSTOM,
}


def normalize_recurrence(value):
    """Convierte el valor de recurrencia leído del disco a su clave interna o `None`."""
    if not value:
        return None
    if value in RECURRENCE_KEYS:
        return value
    return _LEGACY_RECURRENCE_MAP.get(value)


def is_recurrent(recurrence, custom_interval):
    """Indica si un recordatorio debe reprogramarse automáticamente tras dispararse."""
    if custom_interval:
        return True
    return recurrence in RECURRENCE_KEYS


def next_occurrence(reminder_time, recurrence, custom_interval, after=None):
    """Devuelve la siguiente ocurrencia estrictamente posterior a ``after``.

    Al reiniciar NVDA, un recordatorio puede llevar varios periodos vencido. Avanzar
    sólo un periodo provocaba una notificación por segundo hasta alcanzar el presente.
    """
    if after is None:
        after = reminder_time

    if custom_interval:
        interval = timedelta(minutes=custom_interval)
        elapsed = after - reminder_time
        periods = max(1, int(elapsed // interval) + 1)
        return reminder_time + interval * periods

    next_time = reminder_time
    while next_time <= after:
        if recurrence == RECURRENCE_DAILY:
            next_time += timedelta(days=1)
        elif recurrence == RECURRENCE_WEEKLY:
            next_time += timedelta(weeks=1)
        elif recurrence == RECURRENCE_MONTHLY:
            next_time = add_month(next_time)
        else:
            return reminder_time
    return next_time


def add_month(date):
    """Suma un mes a `date` ajustando el día si el mes destino tiene menos días."""
    month = date.month + 1 if date.month < 12 else 1
    year = date.year if date.month < 12 else date.year + 1
    day = date.day
    while day > 0:
        try:
            return date.replace(year=year, month=month, day=day)
        except ValueError:
            day -= 1
    return date
