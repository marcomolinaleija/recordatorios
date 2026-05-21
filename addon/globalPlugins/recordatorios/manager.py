# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Gestión y persistencia de los recordatorios + hilo de verificación."""

import json
import os
import threading
from datetime import datetime, timedelta

import wx

import addonHandler
import config
import globalVars
import gui
import tones
import ui
from nvwave import playWaveFile

addonHandler.initTranslation()

from .constants import (
    ALL_TASKS_COMPLETED_MESSAGE,
    DEFAULT_SNOOZE_MINUTES,
    ID_DELETE,
    ID_REVIEW_SNOOZE,
    ID_SNOOZE,
    INCOMPLETE_TASKS_MESSAGE,
    REMINDER_DELETED_MESSAGE,
    TASK_COMPLETED_STATUS,
    TASK_PENDING_STATUS,
)
from .recurrence import is_recurrent, next_occurrence, normalize_recurrence


class ReminderManager:
    """Gestiona la lista de recordatorios y su verificación en segundo plano."""

    def __init__(self):
        self.reminders = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.file_path = os.path.join(globalVars.appArgs.configPath, "recordatorios.json")
        self.load_reminders()
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    # --- API pública (segura desde el hilo de UI) ---

    def add_reminder(self, message, reminder_time, recurrence=None, sound_file=None,
                     custom_interval=None, tasks=None):
        if tasks is None:
            tasks = []
        message_lower = message.lower()
        with self._lock:
            for existing in self.reminders:
                if existing[0].lower() == message_lower:
                    ui.message(_("Ya existe un recordatorio con el nombre '{}'").format(message))
                    return
            self.reminders.append((message, reminder_time, recurrence, sound_file, custom_interval, tasks))
            self._save_unlocked()

        now = datetime.now()
        if reminder_time.date() == now.date():
            ui.message(_("Recordatorio agregado para {time}").format(time=reminder_time.strftime('%H:%M')))
        else:
            ui.message(_("Recordatorio agregado para el {date} a las {time}").format(
                date=reminder_time.strftime('%d/%m/%Y'),
                time=reminder_time.strftime('%H:%M'),
            ))

    def update_reminder(self, index, new_reminder_time, new_recurrence=None,
                        new_sound_file=None, new_custom_interval=None, new_tasks=None):
        with self._lock:
            if not (0 <= index < len(self.reminders)):
                return False
            message = self.reminders[index][0]
            self.reminders[index] = (
                message, new_reminder_time, new_recurrence,
                new_sound_file, new_custom_interval, new_tasks,
            )
            self._save_unlocked()
            return True

    def remove_at(self, index):
        """Elimina el recordatorio en el índice indicado. Devuelve la tupla o `None`."""
        with self._lock:
            if not (0 <= index < len(self.reminders)):
                return None
            removed = self.reminders.pop(index)
            self._save_unlocked()
            return removed

    def snapshot(self):
        """Copia segura de la lista para iterar desde el hilo de UI."""
        with self._lock:
            return list(self.reminders)

    # --- Hilo de verificación ---

    def _check_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_due_reminders()
            except Exception:
                pass
            if self._stop_event.wait(1.0):
                break

    def _check_due_reminders(self):
        now = datetime.now()
        due = []
        with self._lock:
            for i, reminder in enumerate(self.reminders):
                if reminder[1] <= now:
                    due.append((i, reminder))
            # Procesar en orden inverso para que `pop` no altere los índices pendientes.
            for index, reminder in reversed(due):
                message, reminder_time, recurrence, sound_file, custom_interval, tasks = reminder
                if is_recurrent(recurrence, custom_interval):
                    new_time = next_occurrence(reminder_time, recurrence, custom_interval)
                    self.reminders[index] = (
                        message, new_time, recurrence, sound_file, custom_interval, tasks,
                    )
                else:
                    # Si tiene pendientes, se reinsertará desde el diálogo del hilo de UI.
                    self.reminders.pop(index)
            if due:
                self._save_unlocked()

        # Notificaciones y diálogos fuera del lock para no bloquear escritores.
        for _index, reminder in due:
            if self._stop_event.is_set():
                return
            message, reminder_time, recurrence, sound_file, custom_interval, tasks = reminder
            self._notify(message, sound_file, tasks)
            if not is_recurrent(recurrence, custom_interval):
                has_incomplete = bool(tasks) and any(not t.get('completed') for t in tasks)
                if has_incomplete:
                    wx.CallAfter(self._show_incomplete_task_dialog, reminder)

    def _notify(self, message, sound_file=None, tasks=None):
        tasks = tasks or []
        try:
            interval = int(config.conf["remindersConfig"]["notificationInterval"])
            num_times = int(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"])
        except (KeyError, ValueError, TypeError):
            interval, num_times = 10, 1

        all_completed = all(t.get('completed') for t in tasks) if tasks else True

        for i in range(num_times):
            text = _("Recordatorio: {}").format(message)
            if tasks:
                lines = [
                    "- {status} {desc}".format(
                        status=TASK_COMPLETED_STATUS if t.get('completed') else TASK_PENDING_STATUS,
                        desc=t.get('description', ''),
                    )
                    for t in tasks
                ]
                text += "\n" + _("Tareas:") + "\n" + "\n".join(lines)
                text += "\n" + (ALL_TASKS_COMPLETED_MESSAGE if all_completed else INCOMPLETE_TASKS_MESSAGE).format(message)

            ui.message(text)

            if sound_file and os.path.exists(sound_file):
                playWaveFile(sound_file)
            else:
                tones.beep(440, 500)

            if i < num_times - 1:
                if self._stop_event.wait(interval):
                    return

    def _show_incomplete_task_dialog(self, reminder_data):
        """Diálogo en el hilo de UI para gestionar un recordatorio no recurrente con pendientes."""
        # Importación local para evitar dependencia circular con el paquete `ui`.
        from .ui.incomplete_task_dialog import IncompleteTaskDialog
        from .ui.snooze_dialog import SnoozeDialog

        message, _original_time, recurrence, sound_file, custom_interval, tasks = reminder_data
        dialog = IncompleteTaskDialog(gui.mainFrame, message)
        try:
            result = dialog.ShowModal()
        finally:
            dialog.Destroy()

        if result == ID_DELETE:
            ui.message(REMINDER_DELETED_MESSAGE.format(message))
            return

        if result == ID_REVIEW_SNOOZE:
            self._snooze_minutes(message, DEFAULT_SNOOZE_MINUTES, recurrence, sound_file, custom_interval, tasks)
            # Translators: Confirmation that the reminder was snoozed and suggestion to manage tasks from the menu.
            ui.message(_("Recordatorio pospuesto por {} minutos. Puedes gestionar las tareas desde el menú Herramientas.").format(DEFAULT_SNOOZE_MINUTES))
            return

        if result == ID_SNOOZE:
            snooze_dialog = SnoozeDialog(gui.mainFrame)
            try:
                if snooze_dialog.ShowModal() == wx.ID_OK:
                    minutes = snooze_dialog.get_minutes()
                else:
                    minutes = DEFAULT_SNOOZE_MINUTES
            finally:
                snooze_dialog.Destroy()
            self._snooze_minutes(message, minutes, recurrence, sound_file, custom_interval, tasks)
            # Translators: Confirmation message that the reminder has been snoozed for a custom amount of time.
            ui.message(_("Recordatorio pospuesto por {} minutos.").format(minutes))
            return

        # Diálogo cerrado o cancelado: posponer por el valor por defecto para evitar bucle inmediato.
        self._snooze_minutes(message, DEFAULT_SNOOZE_MINUTES, recurrence, sound_file, custom_interval, tasks)

    def _snooze_minutes(self, message, minutes, recurrence, sound_file, custom_interval, tasks):
        new_time = datetime.now() + timedelta(minutes=minutes)
        with self._lock:
            self.reminders.append((message, new_time, recurrence, sound_file, custom_interval, tasks))
            self._save_unlocked()

    # --- Persistencia ---

    def _save_unlocked(self):
        """Persiste la lista. Requiere `self._lock` adquirido."""
        data = [
            (msg, dt.strftime('%Y-%m-%d %H:%M'), rec, sound, interval, tasks)
            for msg, dt, rec, sound, interval, tasks in self.reminders
        ]
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError:
            pass

    def load_reminders(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        loaded = []
        for item in raw:
            if not isinstance(item, (list, tuple)):
                continue
            if len(item) == 5:
                msg, time_str, rec, sound, custom_interval = item
                tasks = []
            elif len(item) == 6:
                msg, time_str, rec, sound, custom_interval, tasks = item
            else:
                continue
            try:
                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            except (TypeError, ValueError):
                continue
            loaded.append((msg, dt, normalize_recurrence(rec), sound, custom_interval, tasks or []))

        with self._lock:
            self.reminders = loaded
            # Re-guardamos para persistir la migración de claves de recurrencia.
            self._save_unlocked()
