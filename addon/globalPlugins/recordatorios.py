# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

import json
import os
import threading
from datetime import datetime, timedelta

import wx
import wx.adv

import addonHandler
import config
import globalPluginHandler
import globalVars
import gui
import scriptHandler
import tones
import ui
from gui import settingsDialogs
from nvwave import playWaveFile

addonHandler.initTranslation()


# --- Constantes traducibles ---
DELETE_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas eliminar:")
DELETE_REMINDER_TITLE = _("Eliminar recordatorio")
REMINDER_DELETED_MESSAGE = _("El recordatorio '{}' ha sido eliminado.")
REMINDER_DELETED_TITLE = _("Recordatorio eliminado")

RESCHEDULE_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas reprogramar:")
RESCHEDULE_REMINDER_TITLE = _("Reprogramar recordatorio")
REMINDER_RESCHEDULED_MESSAGE = _("El recordatorio '{}' ha sido reprogramado para el {date} a las {time}.")
REMINDER_RESCHEDULED_TITLE = _("Recordatorio reprogramado")
NO_REMINDERS_TO_RESCHEDULE_MESSAGE = _("No hay recordatorios para reprogramar.")

TASK_REMINDER_LABEL = _("&Tareas (una por línea):")
TASK_COMPLETED_STATUS = _("[Completada]")
TASK_PENDING_STATUS = _("[Pendiente]")
MANAGE_TASKS_MESSAGE = _("Selecciona el recordatorio cuyas tareas deseas gestionar:")
MANAGE_TASKS_TITLE = _("Gestionar Tareas del Recordatorio")
NO_REMINDERS_WITH_TASKS_MESSAGE = _("No hay recordatorios con tareas para gestionar.")
ALL_TASKS_COMPLETED_MESSAGE = _("Todas las tareas del recordatorio '{}' han sido completadas.")
INCOMPLETE_TASKS_MESSAGE = _("El recordatorio '{}' tiene tareas incompletas. Por favor, revísalas.")
UPDATE_TASKS_MESSAGE = _("Tareas actualizadas correctamente.")


# --- Recurrencia ---
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


# IDs para el diálogo de tareas incompletas.
ID_DELETE = wx.NewIdRef()
ID_REVIEW_SNOOZE = wx.NewIdRef()
ID_SNOOZE = wx.NewIdRef()

# Minutos por defecto al posponer un recordatorio con tareas pendientes.
DEFAULT_SNOOZE_MINUTES = 10


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

    def add_reminder(self, message, reminder_time, recurrence=None, sound_file=None, custom_interval=None, tasks=None):
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
                if self._is_recurrent(recurrence, custom_interval):
                    new_time = self._next_occurrence(reminder_time, recurrence, custom_interval)
                    self.reminders[index] = (
                        message, new_time, recurrence, sound_file, custom_interval, tasks,
                    )
                else:
                    # Tanto si tiene tareas pendientes como si no, lo retiramos.
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
            if not self._is_recurrent(recurrence, custom_interval):
                has_incomplete = bool(tasks) and any(not t.get('completed') for t in tasks)
                if has_incomplete:
                    wx.CallAfter(self._show_incomplete_task_dialog, reminder)

    @staticmethod
    def _is_recurrent(recurrence, custom_interval):
        if custom_interval:
            return True
        return recurrence in RECURRENCE_KEYS

    @staticmethod
    def _next_occurrence(reminder_time, recurrence, custom_interval):
        if custom_interval:
            return reminder_time + timedelta(minutes=custom_interval)
        if recurrence == RECURRENCE_DAILY:
            return reminder_time + timedelta(days=1)
        if recurrence == RECURRENCE_WEEKLY:
            return reminder_time + timedelta(weeks=1)
        if recurrence == RECURRENCE_MONTHLY:
            return ReminderManager._add_month(reminder_time)
        # Sin recurrencia válida; devolver la misma fecha (la lógica de llamada lo retira).
        return reminder_time

    @staticmethod
    def _add_month(date):
        month = date.month + 1 if date.month < 12 else 1
        year = date.year if date.month < 12 else date.year + 1
        day = date.day
        # Manejar meses con menos días (p. ej. del 31 de enero pasar al último de febrero).
        while day > 0:
            try:
                return date.replace(year=year, month=month, day=day)
            except ValueError:
                day -= 1
        return date

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


class ReminderApp(wx.Frame):
    """Ventana principal para añadir un recordatorio."""

    def __init__(self, reminder_manager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.SetTitle(_("Añadir recordatorio"))
        self.SetSize((400, 550))
        self.reminder_manager = reminder_manager
        self.sound_folder = None
        self.selected_sound = None

        self.panel = wx.Panel(self)
        self._create_interface()
        self._setup_accelerators()
        self.Bind(wx.EVT_CLOSE, self.close)
        self.date_picker.SetValue(wx.DateTime.Now())
        self._load_sound_config()

    # --- Persistencia de la configuración de sonidos ---

    def _sound_config_path(self):
        return os.path.join(globalVars.appArgs.configPath, "sonidos_recordatorios.json")

    def _save_sound_config(self):
        try:
            with open(self._sound_config_path(), 'w', encoding='utf-8') as f:
                json.dump({
                    "sound_folder": self.sound_folder,
                    "selected_sound": self.selected_sound,
                }, f, ensure_ascii=False)
        except OSError:
            pass

    def _load_sound_config(self):
        path = self._sound_config_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        self.sound_folder = data.get("sound_folder")
        self.selected_sound = data.get("selected_sound")
        if self.sound_folder and os.path.isdir(self.sound_folder):
            self._load_sounds_from_folder()
            if self.selected_sound:
                basename = os.path.basename(self.selected_sound)
                if basename in self.sound_choice.GetItems():
                    self.sound_choice.SetStringSelection(basename)
        else:
            self.sound_folder = None
            self.selected_sound = None
            self._save_sound_config()

    # --- Construcción de la UI ---

    def _create_interface(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Translators: Etiqueta para el mensaje del recordatorio.
        sizer.Add(wx.StaticText(self.panel, label=_("&Mensaje del Recordatorio:")), 0, wx.ALL | wx.EXPAND, 5)
        self.message_field = wx.TextCtrl(self.panel)
        sizer.Add(self.message_field, 0, wx.ALL | wx.EXPAND, 5)

        sizer.Add(wx.StaticText(self.panel, label=TASK_REMINDER_LABEL), 0, wx.ALL | wx.EXPAND, 5)
        self.tasks_field = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE | wx.TE_DONTWRAP)
        sizer.Add(self.tasks_field, 1, wx.ALL | wx.EXPAND, 5)

        # Translators: Casilla para activar la selección de una fecha específica.
        self.specific_date_check = wx.CheckBox(self.panel, label=_("&Usar fecha específica"))
        sizer.Add(self.specific_date_check, 0, wx.ALL | wx.EXPAND, 5)
        self.specific_date_check.Bind(wx.EVT_CHECKBOX, self._toggle_specific_date)

        # Translators: Instrucciones para el selector de fecha.
        self.date_label = wx.StaticText(self.panel, label=_("Selecciona una fecha, utilizando flechas izquierda/derecha para moverse entre día, mes y año, y flechas arriba/abajo para modificar los valores:"))
        sizer.Add(self.date_label, 0, wx.ALL | wx.EXPAND, 5)
        self.date_label.Hide()

        self.date_picker = wx.adv.DatePickerCtrl(self.panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        sizer.Add(self.date_picker, 0, wx.ALL | wx.EXPAND, 5)
        self.date_picker.Hide()
        self.date_picker.Bind(wx.EVT_KEY_DOWN, self._on_date_key)
        self.date_picker.Bind(wx.adv.EVT_DATE_CHANGED, self._on_date_changed)
        self.current_date_component = "day"
        self.previous_date = self.date_picker.GetValue()

        # Translators: Etiqueta para la hora (formato 24h).
        sizer.Add(wx.StaticText(self.panel, label=_("&Hora (formato 24h):")), 0, wx.ALL | wx.EXPAND, 5)
        self.hours_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(24)], style=wx.CB_DROPDOWN)
        sizer.Add(self.hours_field, 0, wx.ALL | wx.EXPAND, 5)

        # Translators: Etiqueta para los minutos.
        sizer.Add(wx.StaticText(self.panel, label=_("&Minutos:")), 0, wx.ALL | wx.EXPAND, 5)
        self.minutes_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(60)], style=wx.CB_DROPDOWN)
        sizer.Add(self.minutes_field, 0, wx.ALL | wx.EXPAND, 5)

        # Translators: Casilla para marcar el recordatorio como recurrente.
        self.recurrence_check = wx.CheckBox(self.panel, label=_("&Recordatorio recurrente"))
        sizer.Add(self.recurrence_check, 0, wx.ALL | wx.EXPAND, 5)
        self.recurrence_check.Bind(wx.EVT_CHECKBOX, self._toggle_recurrence)

        # Translators: Etiqueta que precede al selector de frecuencia.
        self.recurrence_label = wx.StaticText(self.panel, label=_("Selecciona la frecuencia con la que llegará el recordatorio."))
        sizer.Add(self.recurrence_label, 0, wx.ALL | wx.EXPAND, 5)
        self.recurrence_label.Hide()

        self.recurrence_choice = wx.ComboBox(self.panel, choices=recurrence_labels(), style=wx.CB_READONLY)
        sizer.Add(self.recurrence_choice, 0, wx.ALL | wx.EXPAND, 5)
        self.recurrence_choice.SetSelection(0)
        self.recurrence_choice.Bind(wx.EVT_COMBOBOX, self._on_recurrence_selection)
        self.recurrence_choice.Hide()

        # Translators: Etiqueta para el intervalo en minutos de la recurrencia personalizada.
        self.custom_interval_label = wx.StaticText(self.panel, label=_("Intervalo de recurrencia personalizada (en minutos):"))
        sizer.Add(self.custom_interval_label, 0, wx.ALL | wx.EXPAND, 5)
        self.custom_interval_label.Hide()
        self.custom_interval_field = wx.TextCtrl(self.panel)
        sizer.Add(self.custom_interval_field, 0, wx.ALL | wx.EXPAND, 5)
        self.custom_interval_field.Hide()

        # Translators: Casilla para activar un sonido personalizado.
        self.custom_sound_check = wx.CheckBox(self.panel, label=_("&Usar sonido personalizado"))
        sizer.Add(self.custom_sound_check, 0, wx.ALL | wx.EXPAND, 5)
        self.custom_sound_check.Bind(wx.EVT_CHECKBOX, self._toggle_custom_sound)

        # Translators: Etiqueta que precede al selector de sonido.
        self.select_sound_label = wx.StaticText(self.panel, label=_("Selecciona un sonido de la lista."))
        sizer.Add(self.select_sound_label, 0, wx.ALL | wx.EXPAND, 5)
        self.select_sound_label.Hide()
        self.sound_choice = wx.ComboBox(self.panel, choices=[], style=wx.CB_READONLY)
        sizer.Add(self.sound_choice, 0, wx.ALL | wx.EXPAND, 5)
        self.sound_choice.Hide()

        # Translators: Botón para reproducir el sonido seleccionado.
        self.play_button = wx.Button(self.panel, label=_("Reproducir  ctrl+p"))
        sizer.Add(self.play_button, 0, wx.ALL | wx.CENTER, 5)
        self.play_button.Bind(wx.EVT_BUTTON, self._on_play_sound)
        self.play_button.Hide()

        # Translators: Botón para seleccionar la carpeta de sonidos.
        self.select_folder_btn = wx.Button(self.panel, label=_("Seleccionar carpeta de sonidos  ctrl+f"))
        sizer.Add(self.select_folder_btn, 0, wx.ALL | wx.CENTER, 5)
        self.select_folder_btn.Bind(wx.EVT_BUTTON, self._on_select_folder)
        self.select_folder_btn.Hide()

        # Translators: Botón para guardar el recordatorio.
        add_button = wx.Button(self.panel, label=_("&Agregar Recordatorio"))
        sizer.Add(add_button, 0, wx.ALL | wx.CENTER, 5)
        add_button.Bind(wx.EVT_BUTTON, self._on_add_reminder)

        # Translators: Botón de donación.
        donate_button = wx.Button(self.panel, label=_("&Donar al desarrollador del complemento"))
        sizer.Add(donate_button, 0, wx.ALL | wx.CENTER, 5)
        donate_button.Bind(wx.EVT_BUTTON, self._on_donate)

        # Translators: Botón para cerrar la ventana.
        cancel_button = wx.Button(self.panel, label=_("Salir  ctrl+q"))
        sizer.Add(cancel_button, 0, wx.ALL | wx.CENTER, 5)
        cancel_button.Bind(wx.EVT_BUTTON, self.close)

        self.panel.SetSizer(sizer)

    def _setup_accelerators(self):
        load_folder = wx.NewIdRef()
        play_file = wx.NewIdRef()
        close_window = wx.NewIdRef()
        close_window_esc = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self._on_select_folder, id=load_folder)
        self.Bind(wx.EVT_MENU, self._on_play_sound, id=play_file)
        self.Bind(wx.EVT_MENU, self.close, id=close_window)
        self.Bind(wx.EVT_MENU, self.close, id=close_window_esc)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("F"), load_folder),
            (wx.ACCEL_CTRL, ord("P"), play_file),
            (wx.ACCEL_CTRL, ord("Q"), close_window),
            (wx.ACCEL_NORMAL, wx.WXK_ESCAPE, close_window_esc),
        ]))

    # --- Manejadores de eventos ---

    def _toggle_specific_date(self, event):
        show = self.specific_date_check.IsChecked()
        self.date_picker.Show(show)
        self.date_label.Show(show)
        self.panel.Layout()

    def _toggle_recurrence(self, event):
        show = self.recurrence_check.IsChecked()
        self.recurrence_choice.Show(show)
        self.recurrence_label.Show(show)
        if not show:
            self.custom_interval_field.Hide()
            self.custom_interval_label.Hide()
        self.panel.Layout()

    def _on_date_key(self, event):
        key_code = event.GetKeyCode()
        date = self.date_picker.GetValue()
        if key_code == wx.WXK_LEFT:
            if self.current_date_component == "month":
                self.current_date_component = "day"
                ui.message(_("Día: {}").format(date.GetDay()))
            elif self.current_date_component == "year":
                self.current_date_component = "month"
                ui.message(_("Mes: {}").format(date.GetMonth() + 1))
        elif key_code == wx.WXK_RIGHT:
            if self.current_date_component == "day":
                self.current_date_component = "month"
                ui.message(_("Mes: {}").format(date.GetMonth() + 1))
            elif self.current_date_component == "month":
                self.current_date_component = "year"
                ui.message(_("Año: {}").format(date.GetYear()))
        elif key_code in (wx.WXK_UP, wx.WXK_DOWN):
            self.previous_date = date
        event.Skip()

    def _on_date_changed(self, event):
        new_date = self.date_picker.GetValue()
        old_date = self.previous_date
        if new_date.GetDay() != old_date.GetDay():
            ui.message(_("Día: {}").format(new_date.GetDay()))
            self.current_date_component = "day"
        elif new_date.GetMonth() != old_date.GetMonth():
            ui.message(_("Mes: {}").format(new_date.GetMonth() + 1))
            self.current_date_component = "month"
        elif new_date.GetYear() != old_date.GetYear():
            ui.message(_("Año: {}").format(new_date.GetYear()))
            self.current_date_component = "year"
        self.previous_date = new_date
        event.Skip()

    def _on_recurrence_selection(self, event):
        is_custom = self.recurrence_choice.GetSelection() == RECURRENCE_KEYS.index(RECURRENCE_CUSTOM)
        self.custom_interval_field.Show(is_custom)
        self.custom_interval_label.Show(is_custom)
        self.panel.Layout()

    def _toggle_custom_sound(self, event):
        show = self.custom_sound_check.IsChecked()
        self.select_folder_btn.Show(show)
        self.play_button.Show(show)
        self.sound_choice.Show(show)
        self.select_sound_label.Show(show)
        self.panel.Layout()

    def _on_select_folder(self, event):
        if not self.custom_sound_check.IsChecked():
            # Translators: Aviso de que la casilla de sonido personalizado no está marcada.
            ui.message(_("La casilla para el sonido personalizado no está marcada."))
            return
        # Translators: Título del diálogo de selección de carpeta de sonidos.
        with wx.DirDialog(self, _("Seleccione la carpeta de sonidos"), style=wx.DD_DEFAULT_STYLE) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                self.sound_folder = dialog.GetPath()
                self._load_sounds_from_folder()
                self._save_sound_config()

    def _load_sounds_from_folder(self):
        if not self.sound_folder or not os.path.isdir(self.sound_folder):
            return
        try:
            sounds = [f for f in os.listdir(self.sound_folder) if f.lower().endswith('.wav')]
        except OSError:
            sounds = []
        self.sound_choice.SetItems(sounds)
        if sounds:
            self.sound_choice.SetSelection(0)
            self.selected_sound = os.path.join(self.sound_folder, sounds[0])
            self._save_sound_config()

    def _on_play_sound(self, event):
        if not self.custom_sound_check.IsChecked():
            ui.message(_("La casilla para el sonido personalizado no está marcada."))
            return
        sound = self.sound_choice.GetValue()
        if not sound or not self.sound_folder:
            return
        sound_path = os.path.join(self.sound_folder, sound)
        if os.path.exists(sound_path):
            playWaveFile(sound_path)

    def _on_add_reminder(self, event):
        custom_interval = None
        raw_interval = self.custom_interval_field.GetValue().strip()
        if raw_interval:
            try:
                custom_interval = int(raw_interval)
                if custom_interval <= 0:
                    raise ValueError
            except ValueError:
                # Translators: Error: el intervalo personalizado debe ser entero positivo.
                wx.MessageBox(_("El intervalo personalizado debe ser un número entero positivo."), _("Error"), wx.ICON_ERROR)
                self.custom_interval_field.SetFocus()
                return

        message = self.message_field.GetValue().strip()
        hours_str = self.hours_field.GetValue().strip()
        minutes_str = self.minutes_field.GetValue().strip()

        tasks = []
        tasks_text = self.tasks_field.GetValue().strip()
        if tasks_text:
            for line in tasks_text.splitlines():
                description = line.strip()
                if description:
                    tasks.append({'description': description, 'completed': False})

        if not message or not hours_str or not minutes_str:
            # Translators: Error: campos obligatorios vacíos.
            wx.MessageBox(_("Parece que alguno de los campos está sin contenido. Mensaje, horas y minutos son obligatorios. Por favor, verifica y vuelve a intentar."), _("Error"), wx.ICON_ERROR)
            self.message_field.SetFocus()
            return

        try:
            hours = int(hours_str)
            minutes = int(minutes_str)
        except ValueError:
            # Translators: Error: horas y minutos no son números válidos.
            wx.MessageBox(_("Las horas y minutos deben de ser números enteros válidos."), _("Error"), wx.ICON_ERROR)
            self.hours_field.SetFocus()
            return

        if not (0 <= hours <= 23) or not (0 <= minutes <= 59):
            # Translators: Error: horas o minutos fuera de rango.
            wx.MessageBox(_("Rango no válido. Las horas deben de estar entre 00 y 23, y los minutos entre 00 y 59."), _("Error"), wx.ICON_ERROR)
            self.hours_field.SetFocus()
            return

        now = datetime.now()
        if self.specific_date_check.IsChecked():
            wx_date = self.date_picker.GetValue()
            reminder_time = datetime(
                wx_date.GetYear(), wx_date.GetMonth() + 1, wx_date.GetDay(),
                hour=hours, minute=minutes,
            )
            if reminder_time < now:
                # Translators: Error: la fecha y hora elegidas están en el pasado.
                wx.MessageBox(_("La fecha y hora seleccionadas están en el pasado. Por favor, selecciona una fecha y hora futura."), _("Error"), wx.ICON_ERROR)
                return
        else:
            reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
            if reminder_time < now:
                reminder_time += timedelta(days=1)

        recurrence = None
        if self.recurrence_check.IsChecked():
            selection = self.recurrence_choice.GetSelection()
            if 0 <= selection < len(RECURRENCE_KEYS):
                recurrence = RECURRENCE_KEYS[selection]
            if recurrence == RECURRENCE_CUSTOM and not custom_interval:
                # Translators: Error: falta el intervalo para la recurrencia personalizada.
                wx.MessageBox(_("Debes especificar un intervalo personalizado para esta recurrencia."), _("Error"), wx.ICON_ERROR)
                self.custom_interval_field.SetFocus()
                return
        else:
            custom_interval = None

        if self.custom_sound_check.IsChecked() and self.sound_choice.GetValue():
            self.selected_sound = os.path.join(self.sound_folder, self.sound_choice.GetValue())
        else:
            self.selected_sound = None

        self.reminder_manager.add_reminder(
            message, reminder_time, recurrence,
            self.selected_sound, custom_interval, tasks,
        )

        self.message_field.Clear()
        self.tasks_field.Clear()
        self.hours_field.SetSelection(-1)
        self.minutes_field.SetSelection(-1)
        self.recurrence_check.SetValue(False)
        self.specific_date_check.SetValue(False)
        self._toggle_specific_date(None)
        self._toggle_recurrence(None)

    def _on_donate(self, event):
        wx.LaunchDefaultBrowser("https://paypal.me/paymentToMl")

    def close(self, event):
        self.Destroy()


def disableInSecureMode(decoratedCls):
    if globalVars.appArgs.secure:
        return globalPluginHandler.GlobalPlugin
    return decoratedCls


@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):

    def __init__(self):
        super().__init__()
        config.conf.spec['remindersConfig'] = {
            "numberOfTimesToNotifyReminder": "integer(default=1)",
            "notificationInterval": "integer(default=10)",
        }
        settingsDialogs.NVDASettingsDialog.categoryClasses.append(remindersConfigPanel)
        self.reminder_manager = ReminderManager()
        self._frame = None
        self._add_to_tools_menu()

    def terminate(self, *args, **kwargs):
        super().terminate(*args, **kwargs)
        try:
            settingsDialogs.NVDASettingsDialog.categoryClasses.remove(remindersConfigPanel)
        except ValueError:
            pass
        if getattr(self, "reminder_manager", None):
            self.reminder_manager.stop()

    def _add_to_tools_menu(self):
        tools_menu = gui.mainFrame.sysTrayIcon.toolsMenu
        sub_menu = wx.Menu()

        items = (
            # Translators: Ítem del submenú para añadir un recordatorio.
            (_("Añadir Recordatorio"), self._open_reminder_window),
            # Translators: Ítem del submenú para ver los recordatorios activos.
            (_("Ver Recordatorios Activos"), self._check_active_reminders),
            # Translators: Ítem del submenú para eliminar un recordatorio.
            (_("Eliminar Recordatorio"), self._delete_reminder),
            # Translators: Ítem del submenú para reprogramar un recordatorio.
            (_("Reprogramar Recordatorio"), self._reschedule_reminder),
            # Translators: Ítem del submenú para gestionar las tareas de un recordatorio.
            (_("Gestionar Tareas"), self._manage_tasks),
        )
        for label, handler in items:
            item = sub_menu.Append(wx.ID_ANY, label)
            gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, handler, item)

        # Translators: Nombre del submenú dentro del menú Herramientas.
        tools_menu.AppendSubMenu(sub_menu, _("&Recordatorios"))

    # --- Helpers de formato ---

    def _format_when(self, reminder_time, now):
        if reminder_time.date() == now.date():
            # Translators: Indica que el recordatorio es hoy.
            return _("hoy a las {time}").format(time=reminder_time.strftime('%H:%M'))
        # Translators: Indica que el recordatorio es en una fecha futura.
        return _("el {date} a las {time}").format(
            date=reminder_time.strftime('%d/%m/%Y'),
            time=reminder_time.strftime('%H:%M'),
        )

    def _format_time_remaining(self, future_datetime):
        diff = future_datetime - datetime.now()
        if diff.total_seconds() < 0:
            # Translators: Indica que el recordatorio ya está en el pasado.
            return _("ya ha pasado")

        total = int(diff.total_seconds())
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        years, days = divmod(days, 365)
        months, days = divmod(days, 30)

        parts = []
        if years:
            # Translators: Cantidad de años restantes (singular y plural).
            parts.append(_("{n} año").format(n=years) if years == 1 else _("{n} años").format(n=years))
        if months:
            # Translators: Cantidad de meses restantes.
            parts.append(_("{n} mes").format(n=months) if months == 1 else _("{n} meses").format(n=months))
        if days:
            # Translators: Cantidad de días restantes.
            parts.append(_("{n} día").format(n=days) if days == 1 else _("{n} días").format(n=days))
        if hours:
            # Translators: Cantidad de horas restantes.
            parts.append(_("{n} hora").format(n=hours) if hours == 1 else _("{n} horas").format(n=hours))
        if minutes:
            # Translators: Cantidad de minutos restantes.
            parts.append(_("{n} minuto").format(n=minutes) if minutes == 1 else _("{n} minutos").format(n=minutes))
        if seconds and not parts:
            # Translators: Cantidad de segundos restantes (solo si es todo lo que queda).
            parts.append(_("{n} segundo").format(n=seconds) if seconds == 1 else _("{n} segundos").format(n=seconds))

        if not parts:
            # Translators: Indica que el recordatorio se activará de inmediato.
            return _("en este momento")
        # Translators: Prefijo "en " antes de un lapso de tiempo (p. ej. "en 5 minutos").
        return _("en ") + ", ".join(parts)

    def _recurrence_text(self, recurrence):
        if recurrence not in RECURRENCE_KEYS:
            return ""
        label = recurrence_labels()[RECURRENCE_KEYS.index(recurrence)]
        # Translators: Sufijo añadido a un recordatorio recurrente. {frequency} es la frecuencia traducida.
        return _(", recurrente {frequency}").format(frequency=label)

    def _build_options(self, reminders):
        now = datetime.now()
        return [
            "{n}: {msg} ({when})".format(
                n=i + 1, msg=reminder[0], when=self._format_when(reminder[1], now),
            )
            for i, reminder in enumerate(reminders)
        ]

    # --- Acciones del menú ---

    def _open_reminder_window(self, event):
        if self._frame:
            try:
                if self._frame.IsShown():
                    self._frame.Raise()
                    return
            except RuntimeError:
                pass
            try:
                self._frame.Destroy()
            except RuntimeError:
                pass
        self._frame = ReminderApp(self.reminder_manager, None)
        self._frame.Show()

    def _check_active_reminders(self, event):
        reminders = self.reminder_manager.snapshot()
        if not reminders:
            # Translators: No hay recordatorios activos.
            ui.message(_("No hay recordatorios activos."))
            return

        now = datetime.now()
        html_parts = []
        for reminder in reminders:
            message, reminder_time, recurrence, _sound, _interval, tasks = reminder
            part = "<h2>{msg}</h2>".format(msg=message)
            # Translators: Etiqueta "Fecha" en la vista de recordatorios activos.
            part += "<p>{label}: {when}{rec}</p>".format(
                label=_("Fecha"),
                when=self._format_when(reminder_time, now),
                rec=self._recurrence_text(recurrence),
            )
            # Translators: Etiqueta "Tiempo restante" en la vista de recordatorios activos.
            part += "<p>{label}: {remaining}</p>".format(
                label=_("Tiempo restante"),
                remaining=self._format_time_remaining(reminder_time),
            )
            if tasks:
                # Translators: Encabezado "Tareas" en la vista de recordatorios activos.
                part += "<h3>{label}:</h3><ol>".format(label=_("Tareas"))
                for task in tasks:
                    status = TASK_COMPLETED_STATUS if task.get('completed') else TASK_PENDING_STATUS
                    part += "<li><strong>{status}</strong> {desc}</li>".format(
                        status=status, desc=task.get('description', ''),
                    )
                part += "</ol>"
            html_parts.append(part)

        # Translators: Título de la ventana con la lista de recordatorios activos.
        ui.browseableMessage("<hr>".join(html_parts), _("Recordatorios activos:"), isHtml=True)

    def _delete_reminder(self, event):
        reminders = self.reminder_manager.snapshot()
        if not reminders:
            # Translators: No hay recordatorios para eliminar.
            ui.message(_("No hay recordatorios para eliminar."))
            return

        dlg = wx.SingleChoiceDialog(
            gui.mainFrame, DELETE_REMINDER_MESSAGE, DELETE_REMINDER_TITLE,
            self._build_options(reminders),
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            removed = self.reminder_manager.remove_at(dlg.GetSelection())
            if removed is None:
                # Translators: El recordatorio ya no existe.
                gui.messageBox(_("El recordatorio seleccionado ya no existe."), _("Error"), wx.ICON_ERROR)
                return
            gui.messageBox(REMINDER_DELETED_MESSAGE.format(removed[0]), REMINDER_DELETED_TITLE)
        finally:
            dlg.Destroy()

    def _reschedule_reminder(self, event):
        reminders = self.reminder_manager.snapshot()
        if not reminders:
            ui.message(NO_REMINDERS_TO_RESCHEDULE_MESSAGE)
            return

        dlg = wx.SingleChoiceDialog(
            gui.mainFrame, RESCHEDULE_REMINDER_MESSAGE, RESCHEDULE_REMINDER_TITLE,
            self._build_options(reminders),
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            selection = dlg.GetSelection()
            if not (0 <= selection < len(reminders)):
                gui.messageBox(_("El recordatorio seleccionado ya no existe."), _("Error"), wx.ICON_ERROR)
                return
            original = reminders[selection]
            original_message = original[0]
            original_time = original[1]
            original_recurrence = original[2]
            original_sound = original[3]
            original_interval = original[4]
            original_tasks = original[5]
        finally:
            dlg.Destroy()

        reschedule_dlg = RescheduleReminderDialog(gui.mainFrame, original_message, original_time)
        try:
            if reschedule_dlg.ShowModal() != wx.ID_OK:
                return
            wx_date = reschedule_dlg.date_picker.GetValue()
            try:
                new_hours = int(reschedule_dlg.hours_field.GetValue().strip())
                new_minutes = int(reschedule_dlg.minutes_field.GetValue().strip())
            except ValueError:
                gui.messageBox(_("Las horas y minutos deben de ser números enteros válidos."), _("Error"), wx.ICON_ERROR)
                return
            new_time = datetime(
                wx_date.GetYear(), wx_date.GetMonth() + 1, wx_date.GetDay(),
                hour=new_hours, minute=new_minutes,
            )
            if new_time < datetime.now():
                # Translators: Error: la nueva fecha es en el pasado.
                gui.messageBox(_("La nueva fecha y hora seleccionadas están en el pasado. Por favor, selecciona una fecha y hora futura."), _("Error"), wx.ICON_ERROR)
                return
            if self.reminder_manager.update_reminder(
                selection, new_time, original_recurrence,
                original_sound, original_interval, original_tasks,
            ):
                gui.messageBox(
                    REMINDER_RESCHEDULED_MESSAGE.format(
                        original_message,
                        date=new_time.strftime('%d/%m/%Y'),
                        time=new_time.strftime('%H:%M'),
                    ),
                    REMINDER_RESCHEDULED_TITLE,
                )
            else:
                # Translators: Error genérico al reprogramar.
                gui.messageBox(_("Ocurrió un error al intentar reprogramar el recordatorio."), _("Error"), wx.ICON_ERROR)
        finally:
            reschedule_dlg.Destroy()

    def _manage_tasks(self, event):
        reminders = self.reminder_manager.snapshot()
        with_tasks = [(i, r) for i, r in enumerate(reminders) if r[5]]
        if not with_tasks:
            ui.message(NO_REMINDERS_WITH_TASKS_MESSAGE)
            return

        options = self._build_options([r for _, r in with_tasks])
        dlg = wx.SingleChoiceDialog(gui.mainFrame, MANAGE_TASKS_MESSAGE, MANAGE_TASKS_TITLE, options)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            selection_in_filtered = dlg.GetSelection()
            original_index, reminder = with_tasks[selection_in_filtered]
            message, reminder_time, recurrence, sound, interval, tasks = reminder
        finally:
            dlg.Destroy()

        manage_dlg = ManageTasksDialog(gui.mainFrame, message, tasks)
        try:
            if manage_dlg.ShowModal() != wx.ID_OK:
                return
            if self.reminder_manager.update_reminder(
                original_index, reminder_time, recurrence,
                sound, interval, manage_dlg.modified_tasks,
            ):
                ui.message(UPDATE_TASKS_MESSAGE)
            else:
                # Translators: Error al actualizar las tareas.
                gui.messageBox(_("Ocurrió un error al actualizar las tareas del recordatorio."), _("Error"), wx.ICON_ERROR)
        finally:
            manage_dlg.Destroy()

    # --- Gestos ---

    @scriptHandler.script(
        # Translators: Descripción del gesto para abrir la ventana de recordatorios.
        description=_("Abrir la ventana de recordatorios"),
        # Translators: Categoría de los gestos del complemento.
        category=_("Recordatorios"),
        gesture=None,
    )
    def script_open_reminder_window(self, gesture):
        self._open_reminder_window(None)

    @scriptHandler.script(
        # Translators: Descripción del gesto para verificar recordatorios activos.
        description=_("Verificar recordatorios activos"),
        category=_("Recordatorios"),
        gesture=None,
    )
    def script_check_active_reminders(self, gesture):
        self._check_active_reminders(None)

    @scriptHandler.script(
        # Translators: Descripción del gesto para abrir el diálogo de eliminar.
        description=_("Lanza el diálogo para eliminar recordatorios"),
        category=_("Recordatorios"),
        gesture=None,
    )
    def script_open_delete_dialog(self, gesture):
        wx.CallAfter(self._delete_reminder, None)

    @scriptHandler.script(
        # Translators: Descripción del gesto para abrir el diálogo de reprogramar.
        description=_("Lanza el diálogo para reprogramar recordatorios"),
        category=_("Recordatorios"),
        gesture=None,
    )
    def script_open_reschedule_dialog(self, gesture):
        wx.CallAfter(self._reschedule_reminder, None)

    @scriptHandler.script(
        # Translators: Descripción del gesto para abrir el diálogo de gestionar tareas.
        description=_("Lanza el diálogo para gestionar tareas de recordatorios"),
        category=_("Recordatorios"),
        gesture=None,
    )
    def script_open_manage_tasks_dialog(self, gesture):
        wx.CallAfter(self._manage_tasks, None)


# --- Diálogos auxiliares ---

class RescheduleReminderDialog(wx.Dialog):
    """Diálogo para elegir la nueva fecha y hora de un recordatorio."""

    def __init__(self, parent, message, original_time):
        # Translators: Título del diálogo de reprogramación. {} es el nombre del recordatorio.
        super().__init__(parent, title=_("Reprogramar: {}").format(message))
        self.panel = wx.Panel(self)
        self._create_interface(original_time)
        self.SetSize((350, 300))

    def _create_interface(self, original_time):
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Instrucciones del diálogo de reprogramación.
        sizer.Add(wx.StaticText(self.panel, label=_("Selecciona la nueva fecha y hora para el recordatorio:")),
                  0, wx.ALL | wx.EXPAND, 5)

        self.date_picker = wx.adv.DatePickerCtrl(self.panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
        sizer.Add(self.date_picker, 0, wx.ALL | wx.EXPAND, 5)
        wx_original = wx.DateTime()
        # wx.DateTime usa meses indexados en 0.
        wx_original.Set(original_time.day, original_time.month - 1, original_time.year)
        self.date_picker.SetValue(wx_original)

        # Translators: Etiqueta para la nueva hora.
        sizer.Add(wx.StaticText(self.panel, label=_("Nueva Hora (formato 24h):")), 0, wx.ALL | wx.EXPAND, 5)
        self.hours_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(24)], style=wx.CB_DROPDOWN)
        sizer.Add(self.hours_field, 0, wx.ALL | wx.EXPAND, 5)
        self.hours_field.SetSelection(original_time.hour)

        # Translators: Etiqueta para los nuevos minutos.
        sizer.Add(wx.StaticText(self.panel, label=_("Nuevos Minutos:")), 0, wx.ALL | wx.EXPAND, 5)
        self.minutes_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(60)], style=wx.CB_DROPDOWN)
        sizer.Add(self.minutes_field, 0, wx.ALL | wx.EXPAND, 5)
        self.minutes_field.SetSelection(original_time.minute)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(wx.Button(self.panel, wx.ID_OK, _("Aceptar")))
        btn_sizer.AddButton(wx.Button(self.panel, wx.ID_CANCEL, _("Cancelar")))
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.CENTER, 5)

        self.panel.SetSizer(sizer)


class ManageTasksDialog(wx.Dialog):
    """Diálogo para marcar/desmarcar las tareas de un recordatorio como completadas."""

    def __init__(self, parent, reminder_message, tasks):
        # Translators: Título del diálogo de gestión de tareas. {} es el nombre del recordatorio.
        super().__init__(parent, title=_("Gestionar Tareas: {}").format(reminder_message))
        self.modified_tasks = [task.copy() for task in tasks]
        self._checkboxes = []
        self.panel = wx.Panel(self)
        self._create_interface()
        self.SetSize((450, 400))

    def _create_interface(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        if not self.modified_tasks:
            # Translators: Mensaje cuando el recordatorio no tiene tareas asociadas.
            sizer.Add(wx.StaticText(self.panel, label=_("Este recordatorio no tiene tareas.")),
                      0, wx.ALL | wx.EXPAND, 5)
        else:
            for task in self.modified_tasks:
                checkbox = wx.CheckBox(self.panel, label=task.get('description', ''))
                checkbox.SetValue(bool(task.get('completed')))
                checkbox.Bind(wx.EVT_CHECKBOX, self._on_toggle)
                self._checkboxes.append(checkbox)
                sizer.Add(checkbox, 0, wx.ALL | wx.EXPAND, 5)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(wx.Button(self.panel, wx.ID_OK, _("Aceptar")))
        btn_sizer.AddButton(wx.Button(self.panel, wx.ID_CANCEL, _("Cancelar")))
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.CENTER, 5)

        self.panel.SetSizer(sizer)

    def _on_toggle(self, event):
        checkbox = event.GetEventObject()
        index = self._checkboxes.index(checkbox)
        self.modified_tasks[index]['completed'] = checkbox.GetValue()
        event.Skip()


class SnoozeDialog(wx.Dialog):
    """Diálogo para elegir cuántos minutos posponer un recordatorio."""

    def __init__(self, parent):
        # Translators: Título del diálogo para posponer un recordatorio.
        super().__init__(parent, title=_("Posponer recordatorio"))
        self.panel = wx.Panel(self)
        self._minutes = DEFAULT_SNOOZE_MINUTES
        self._create_interface()
        self.SetSize((300, 150))
        self.minutes_spin.SetFocus()

    def _create_interface(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Etiqueta para el campo de minutos a posponer.
        sizer.Add(wx.StaticText(self.panel, label=_("Posponer por (minutos):")), 0, wx.ALL | wx.EXPAND, 10)

        self.minutes_spin = wx.SpinCtrl(self.panel, value=str(DEFAULT_SNOOZE_MINUTES), min=1, max=1440)
        sizer.Add(self.minutes_spin, 0, wx.ALL | wx.EXPAND, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(self.panel, wx.ID_OK, _("Aceptar"))
        btn_sizer.AddButton(ok_button)
        btn_sizer.AddButton(wx.Button(self.panel, wx.ID_CANCEL, _("Cancelar")))
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 1, wx.ALL | wx.CENTER, 10)

        self.panel.SetSizer(sizer)
        ok_button.Bind(wx.EVT_BUTTON, self._on_ok)

    def _on_ok(self, event):
        self._minutes = self.minutes_spin.GetValue()
        self.EndModal(wx.ID_OK)

    def get_minutes(self):
        return self._minutes


class IncompleteTaskDialog(wx.Dialog):
    """Diálogo que se muestra cuando un recordatorio con tareas pendientes llega a su hora."""

    def __init__(self, parent, message):
        # Translators: Título del diálogo de tareas pendientes.
        super().__init__(parent, title=_("Tareas pendientes"))
        self.panel = wx.Panel(self)
        self._create_interface(message)
        self.SetSize((450, 200))

    def _create_interface(self, message):
        sizer = wx.BoxSizer(wx.VERTICAL)
        # Translators: Pregunta del diálogo de tareas pendientes. {} es el nombre del recordatorio.
        sizer.Add(wx.StaticText(self.panel, label=_("El recordatorio '{}' tiene tareas pendientes. ¿Qué deseas hacer?").format(message)),
                  0, wx.ALL | wx.EXPAND, 10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Translators: Botón para eliminar el recordatorio aun con tareas pendientes.
        delete_button = wx.Button(self.panel, ID_DELETE, _("Eliminar de todos modos"))
        # Translators: Botón para revisar tareas (pospone el recordatorio 10 minutos).
        review_button = wx.Button(self.panel, ID_REVIEW_SNOOZE, _("Revisar tareas (posponer 10 min)"))
        # Translators: Botón para abrir el diálogo de tiempo personalizado de posponer.
        snooze_button = wx.Button(self.panel, ID_SNOOZE, _("Posponer..."))
        button_sizer.Add(delete_button, 0, wx.ALL, 5)
        button_sizer.Add(review_button, 0, wx.ALL, 5)
        button_sizer.Add(snooze_button, 0, wx.ALL, 5)
        sizer.Add(button_sizer, 0, wx.CENTER)
        self.panel.SetSizer(sizer)

        delete_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(ID_DELETE))
        review_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(ID_REVIEW_SNOOZE))
        snooze_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(ID_SNOOZE))


class remindersConfigPanel(settingsDialogs.SettingsPanel):
    # Translators: Título del panel de configuración del complemento.
    title = _("Configuración de recordatorios")

    def makeSettings(self, sizer):
        helper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)
        # Translators: Etiqueta para el número de notificaciones.
        helper.addItem(wx.StaticText(self, label=_("Selecciona el número de notificaciones que llegarán para el recordatorio.")))
        self.numberOfTimesToNotifyReminder = helper.addItem(
            wx.ComboBox(self, choices=["1", "2", "3", "4"], style=wx.CB_READONLY)
        )
        self.numberOfTimesToNotifyReminder.SetStringSelection(
            str(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"])
        )
        # Translators: Etiqueta para el intervalo entre notificaciones (segundos).
        helper.addItem(wx.StaticText(self, label=_("Selecciona el intervalo de tiempo para las notificaciones (en segundos).")))
        self.notificationInterval = helper.addItem(
            wx.ComboBox(self, choices=["5", "10", "20", "40", "60"], style=wx.CB_READONLY)
        )
        self.notificationInterval.SetStringSelection(
            str(config.conf["remindersConfig"]["notificationInterval"])
        )

    def onSave(self):
        config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"] = int(
            self.numberOfTimesToNotifyReminder.GetStringSelection()
        )
        config.conf["remindersConfig"]["notificationInterval"] = int(
            self.notificationInterval.GetStringSelection()
        )
