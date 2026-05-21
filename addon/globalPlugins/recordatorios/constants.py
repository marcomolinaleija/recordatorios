# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Constantes traducibles e identificadores compartidos por el complemento."""

import wx

import addonHandler

addonHandler.initTranslation()


# --- Mensajes de eliminación ---
DELETE_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas eliminar:")
DELETE_REMINDER_TITLE = _("Eliminar recordatorio")
REMINDER_DELETED_MESSAGE = _("El recordatorio '{}' ha sido eliminado.")
REMINDER_DELETED_TITLE = _("Recordatorio eliminado")

# --- Mensajes de reprogramación ---
RESCHEDULE_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas reprogramar:")
RESCHEDULE_REMINDER_TITLE = _("Reprogramar recordatorio")
REMINDER_RESCHEDULED_MESSAGE = _("El recordatorio '{}' ha sido reprogramado para el {date} a las {time}.")
REMINDER_RESCHEDULED_TITLE = _("Recordatorio reprogramado")
NO_REMINDERS_TO_RESCHEDULE_MESSAGE = _("No hay recordatorios para reprogramar.")

# --- Mensajes de edición completa ---
EDIT_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas editar:")
EDIT_REMINDER_TITLE = _("Editar recordatorio")
REMINDER_UPDATED_MESSAGE = _("El recordatorio '{}' ha sido actualizado correctamente.")
REMINDER_UPDATED_TITLE = _("Recordatorio actualizado")
NO_REMINDERS_TO_EDIT_MESSAGE = _("No hay recordatorios para editar.")

# --- Mensajes de tareas ---
TASK_REMINDER_LABEL = _("&Tareas (una por línea):")
TASK_COMPLETED_STATUS = _("[Completada]")
TASK_PENDING_STATUS = _("[Pendiente]")
MANAGE_TASKS_MESSAGE = _("Selecciona el recordatorio cuyas tareas deseas gestionar:")
MANAGE_TASKS_TITLE = _("Gestionar Tareas del Recordatorio")
NO_REMINDERS_WITH_TASKS_MESSAGE = _("No hay recordatorios con tareas para gestionar.")
ALL_TASKS_COMPLETED_MESSAGE = _("Todas las tareas del recordatorio '{}' han sido completadas.")
INCOMPLETE_TASKS_MESSAGE = _("El recordatorio '{}' tiene tareas incompletas. Por favor, revísalas.")
UPDATE_TASKS_MESSAGE = _("Tareas actualizadas correctamente.")


# IDs para el diálogo de tareas incompletas.
ID_DELETE = wx.NewIdRef()
ID_REVIEW_SNOOZE = wx.NewIdRef()
ID_SNOOZE = wx.NewIdRef()

# Minutos por defecto al posponer un recordatorio con tareas pendientes.
DEFAULT_SNOOZE_MINUTES = 10
