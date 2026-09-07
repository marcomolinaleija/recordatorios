# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Gestión y persistencia de los recordatorios + hilo de verificación."""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timedelta

import wx

import addonHandler
import config
import globalVars
import gui
import logHandler
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


# Claves que componen un recordatorio. Persistido como dict JSON.
_REMINDER_DEFAULTS = {
    "message": "",
    "id": None,
    "time": None,
    "recurrence": None,
    "sound_file": None,
    "custom_interval": None,
    "tasks": [],
    "pre_notification_minutes": None,
    "pre_notified": False,
    "pending_review": False,
    "google_event_id": None,
}


def new_reminder(message, time, recurrence=None, sound_file=None, custom_interval=None,
                 tasks=None, pre_notification_minutes=None, pre_notified=False,
                 reminder_id=None, pending_review=False, google_event_id=None):
    """Construye un recordatorio con los valores por defecto correctos."""
    return {
        "id": reminder_id or str(uuid.uuid4()),
        "message": message,
        "time": time,
        "recurrence": recurrence,
        "sound_file": sound_file,
        "custom_interval": custom_interval,
        "tasks": list(tasks) if tasks else [],
        "pre_notification_minutes": pre_notification_minutes,
        "pre_notified": pre_notified,
        "pending_review": pending_review,
        "google_event_id": google_event_id,
    }


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
                     custom_interval=None, tasks=None, pre_notification_minutes=None):
        message_lower = message.lower()
        with self._lock:
            for existing in self.reminders:
                if existing["message"].lower() == message_lower:
                    ui.message(_("Ya existe un recordatorio con el nombre '{}'").format(message))
                    return
            self.reminders.append(new_reminder(
                message=message, time=reminder_time, recurrence=recurrence,
                sound_file=sound_file, custom_interval=custom_interval, tasks=tasks,
                pre_notification_minutes=pre_notification_minutes,
            ))
            self._save_unlocked()

        now = datetime.now()
        if reminder_time.date() == now.date():
            ui.message(_("Recordatorio agregado para {time}").format(time=reminder_time.strftime('%H:%M')))
        else:
            ui.message(_("Recordatorio agregado para el {date} a las {time}").format(
                date=reminder_time.strftime('%d/%m/%Y'),
                time=reminder_time.strftime('%H:%M'),
            ))

    def update_reminder(self, reminder_id, **fields):
        """Actualiza los campos indicados del recordatorio con `reminder_id`.

        Reinicia `pre_notified` y `pending_review` automáticamente salvo que se
        pasen explícitamente.
        Retorna True si se actualizó, False si el índice no es válido.
        """
        with self._lock:
            for index, reminder in enumerate(self.reminders):
                if reminder["id"] != reminder_id:
                    continue
                updated = {**reminder, **fields}
                if "pre_notified" not in fields:
                    updated["pre_notified"] = False
                if "pending_review" not in fields:
                    updated["pending_review"] = False
                self.reminders[index] = updated
                self._save_unlocked()
                return True
        return False

    def has_duplicate_message(self, message, ignore_id=None):
        """Indica si otro recordatorio (distinto de `ignore_id`) ya tiene ese nombre."""
        lower = message.lower()
        with self._lock:
            for r in self.reminders:
                if r["id"] == ignore_id:
                    continue
                if r["message"].lower() == lower:
                    return True
        return False

    def remove(self, reminder_id):
        """Elimina el recordatorio por identificador. Devuelve el dict o ``None``."""
        with self._lock:
            for index, reminder in enumerate(self.reminders):
                if reminder["id"] == reminder_id:
                    removed = self.reminders.pop(index)
                    self._save_unlocked()
                    return removed
        return None

    def snapshot(self):
        """Copia segura de la lista para iterar desde el hilo de UI."""
        with self._lock:
            return [dict(r) for r in self.reminders]

    # --- Hilo de verificación ---

    def _check_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_due_reminders()
            except Exception:
                logHandler.log.exception("Error al comprobar los recordatorios pendientes")
            if self._stop_event.wait(1.0):
                break

    def _check_due_reminders(self):
        now = datetime.now()
        due = []
        pre_due = []
        with self._lock:
            for i, reminder in enumerate(self.reminders):
                if reminder.get("pending_review"):
                    continue
                if reminder["time"] <= now:
                    due.append((i, dict(reminder)))
                    continue
                pre_min = reminder.get("pre_notification_minutes")
                if (pre_min is not None
                        and not reminder.get("pre_notified")
                        and reminder["time"] - timedelta(minutes=pre_min) <= now):
                    pre_due.append((i, dict(reminder)))

            # Marcar como pre-notificados antes de salir del lock.
            for i, _r in pre_due:
                self.reminders[i] = {**self.reminders[i], "pre_notified": True}

            # Procesar vencidos en orden inverso para que `pop` no altere índices.
            for index, reminder in reversed(due):
                if is_recurrent(reminder["recurrence"], reminder["custom_interval"]):
                    new_time = next_occurrence(
                        reminder["time"], reminder["recurrence"], reminder["custom_interval"],
                        after=now,
                    )
                    self.reminders[index] = {
                        **self.reminders[index],
                        "time": new_time,
                        "pre_notified": False,
                    }
                else:
                    has_incomplete = bool(reminder["tasks"]) and any(
                        not t.get('completed') for t in reminder["tasks"]
                    )
                    if has_incomplete:
                        # Se conserva hasta que el usuario decida qué hacer en el diálogo.
                        self.reminders[index] = {**self.reminders[index], "pending_review": True}
                    else:
                        self.reminders.pop(index)
            if due or pre_due:
                self._save_unlocked()

        # Pre-notificaciones primero (son los que faltan), después las vencidas.
        for _i, reminder in pre_due:
            if self._stop_event.is_set():
                return
            wx.CallAfter(self._pre_notify, reminder)

        for _i, reminder in due:
            if self._stop_event.is_set():
                return
            wx.CallAfter(self._notify, reminder["message"], reminder["sound_file"], reminder["tasks"])
            if not is_recurrent(reminder["recurrence"], reminder["custom_interval"]):
                has_incomplete = bool(reminder["tasks"]) and any(
                    not t.get('completed') for t in reminder["tasks"]
                )
                if has_incomplete:
                    wx.CallAfter(self._show_incomplete_task_dialog, reminder)

    def _pre_notify(self, reminder):
        """Aviso anticipado: un único mensaje + sonido, sin repeticiones."""
        minutes = reminder.get("pre_notification_minutes") or 0
        message = reminder["message"]
        sound_file = reminder.get("sound_file")

        # Translators: Pre-notificación. {message} es el nombre del recordatorio. {minutes} los minutos restantes.
        text = _("Aviso: el recordatorio '{message}' llegará en {minutes} minutos.").format(
            message=message, minutes=minutes,
        )
        ui.message(text)
        if sound_file and os.path.exists(sound_file):
            playWaveFile(sound_file)
        else:
            # Beep más agudo y corto para distinguir del aviso principal.
            tones.beep(660, 200)

    def _deliver_notification(self, message, sound_file, tasks, all_completed):
        """Entrega un aviso desde el hilo de interfaz sin bloquear el planificador."""
        if self._stop_event.is_set():
            return
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

    def _notify(self, message, sound_file=None, tasks=None):
        """Programa avisos sin bloquear el hilo que detecta recordatorios."""
        tasks = tasks or []
        try:
            interval = int(config.conf["remindersConfig"]["notificationInterval"])
            num_times = int(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"])
        except (KeyError, ValueError, TypeError):
            interval, num_times = 10, 1

        all_completed = all(t.get('completed') for t in tasks) if tasks else True
        for i in range(num_times):
            wx.CallLater(i * interval * 1000, self._deliver_notification, message, sound_file, tasks, all_completed)

    def _show_incomplete_task_dialog(self, reminder):
        """Diálogo en el hilo de UI para gestionar un recordatorio no recurrente con pendientes."""
        # Importación local para evitar dependencia circular con el subpaquete de widgets.
        from .widgets.incomplete_task_dialog import IncompleteTaskDialog
        from .widgets.snooze_dialog import SnoozeDialog

        message = reminder["message"]
        dialog = IncompleteTaskDialog(gui.mainFrame, message)
        try:
            result = dialog.ShowModal()
        finally:
            dialog.Destroy()

        if result == ID_DELETE:
            if self.remove(reminder["id"]):
                ui.message(REMINDER_DELETED_MESSAGE.format(message))
            return

        if result == ID_REVIEW_SNOOZE:
            self._snooze_minutes(reminder, DEFAULT_SNOOZE_MINUTES)
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
            self._snooze_minutes(reminder, minutes)
            # Translators: Confirmation message that the reminder has been snoozed for a custom amount of time.
            ui.message(_("Recordatorio pospuesto por {} minutos.").format(minutes))
            return

        # Diálogo cerrado o cancelado: posponer por el valor por defecto para evitar bucle inmediato.
        self._snooze_minutes(reminder, DEFAULT_SNOOZE_MINUTES)

    def _snooze_minutes(self, reminder, minutes):
        new_time = datetime.now() + timedelta(minutes=minutes)
        self.update_reminder(
            reminder["id"], time=new_time, pre_notified=False, pending_review=False,
        )

    # --- Persistencia ---

    def _save_unlocked(self):
        """Persiste la lista. Requiere `self._lock` adquirido."""
        data = [self._serialize(r) for r in self.reminders]
        temporary_path = "{}.{}.tmp".format(self.file_path, uuid.uuid4().hex)
        try:
            with open(temporary_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary_path, self.file_path)
        except OSError:
            logHandler.log.exception("No se pudo guardar los recordatorios")
            try:
                os.unlink(temporary_path)
            except OSError:
                pass

    @staticmethod
    def _serialize(reminder):
        return {
            "id": reminder["id"],
            "message": reminder["message"],
            "time": reminder["time"].strftime('%Y-%m-%d %H:%M'),
            "recurrence": reminder["recurrence"],
            "sound_file": reminder["sound_file"],
            "custom_interval": reminder["custom_interval"],
            "tasks": reminder["tasks"],
            "pre_notification_minutes": reminder["pre_notification_minutes"],
            "pre_notified": reminder["pre_notified"],
            "pending_review": reminder.get("pending_review", False),
            "google_event_id": reminder.get("google_event_id"),
        }

    def _backup_current_file(self, reason):
        """Conserva el archivo original antes de recuperarse de datos no válidos."""
        backup_path = "{}.{}.{}.bak".format(
            self.file_path, datetime.now().strftime('%Y%m%d-%H%M%S'), uuid.uuid4().hex[:8],
        )
        try:
            shutil.copy2(self.file_path, backup_path)
            logHandler.log.error("Archivo de recordatorios no válido (%s). Copia guardada en %s", reason, backup_path)
        except OSError:
            logHandler.log.exception("No se pudo crear una copia de seguridad de recordatorios")

    def load_reminders(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except json.JSONDecodeError:
            self._backup_current_file("JSON inválido")
            return
        except OSError:
            logHandler.log.exception("No se pudo leer el archivo de recordatorios")
            return

        if not isinstance(raw, list):
            self._backup_current_file("la raíz no es una lista")
            return

        loaded = []
        invalid_entries = False
        for item in raw:
            migrated = self._migrate_entry(item)
            if migrated is not None:
                loaded.append(migrated)
            else:
                invalid_entries = True

        if invalid_entries:
            self._backup_current_file("contiene entradas no válidas")

        with self._lock:
            self.reminders = loaded
            # Re-guardamos para persistir migraciones; el original queda respaldado si hubo entradas inválidas.
            self._save_unlocked()

    @staticmethod
    def _migrate_entry(entry):
        """Acepta dicts (formato nuevo) o listas/tuplas (formato antiguo de 5 o 6 campos)."""
        if isinstance(entry, dict):
            time_str = entry.get("time")
        elif isinstance(entry, (list, tuple)):
            if len(entry) == 5:
                msg, time_str, rec, sound, custom_interval = entry
                tasks = []
            elif len(entry) == 6:
                msg, time_str, rec, sound, custom_interval, tasks = entry
            else:
                return None
            entry = {
                "message": msg,
                "time": time_str,
                "recurrence": rec,
                "sound_file": sound,
                "custom_interval": custom_interval,
                "tasks": tasks or [],
            }
        else:
            return None

        try:
            dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        except (TypeError, ValueError):
            return None

        tasks = entry.get("tasks") or []
        if not isinstance(tasks, list) or not all(isinstance(task, dict) for task in tasks):
            return None
        custom_interval = entry.get("custom_interval")
        if custom_interval is not None:
            if not isinstance(custom_interval, int) or custom_interval <= 0:
                return None
        pre_notification_minutes = entry.get("pre_notification_minutes")
        if pre_notification_minutes is not None:
            if not isinstance(pre_notification_minutes, int) or pre_notification_minutes <= 0:
                return None
        reminder_id = entry.get("id")
        if not isinstance(reminder_id, str) or not reminder_id:
            reminder_id = None

        return new_reminder(
            message=entry.get("message", ""),
            time=dt,
            recurrence=normalize_recurrence(entry.get("recurrence")),
            sound_file=entry.get("sound_file"),
            custom_interval=custom_interval,
            tasks=tasks,
            pre_notification_minutes=pre_notification_minutes,
            pre_notified=bool(entry.get("pre_notified")),
            reminder_id=reminder_id,
            pending_review=bool(entry.get("pending_review")),
            google_event_id=entry.get("google_event_id"),
        )
