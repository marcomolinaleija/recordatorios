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


def next_occurrence(reminder_time, recurrence, custom_interval):
    """Calcula la siguiente hora a la que debe activarse un recordatorio recurrente."""
    if custom_interval:
        return reminder_time + timedelta(minutes=custom_interval)
    if recurrence == RECURRENCE_DAILY:
        return reminder_time + timedelta(days=1)
    if recurrence == RECURRENCE_WEEKLY:
        return reminder_time + timedelta(weeks=1)
    if recurrence == RECURRENCE_MONTHLY:
        return add_month(reminder_time)
    return reminder_time


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
