# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Ventana para crear o editar un recordatorio."""

import json
import os
from datetime import datetime, timedelta

import wx
import wx.adv

import addonHandler
import globalVars
import gui
import ui
from nvwave import playWaveFile

addonHandler.initTranslation()

from ..constants import REMINDER_UPDATED_MESSAGE, REMINDER_UPDATED_TITLE, TASK_REMINDER_LABEL
from ..recurrence import RECURRENCE_CUSTOM, RECURRENCE_KEYS, recurrence_labels


class ReminderApp(wx.Frame):
    """Ventana para añadir o editar un recordatorio.

    Si se pasa `reminder_to_edit=(index, reminder_dict)`, la ventana abre en modo edición:
    pre-rellena los campos, cambia el título y la etiqueta del botón, y al guardar
    llama a `update_reminder` en lugar de `add_reminder`.
    """

    def __init__(self, reminder_manager, *args, reminder_to_edit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.reminder_manager = reminder_manager
        self._edit_target = reminder_to_edit  # tuple (index, reminder_dict) o None
        self.sound_folder = None
        self.selected_sound = None

        if reminder_to_edit:
            self.SetTitle(_("Editar recordatorio"))
        else:
            self.SetTitle(_("Añadir recordatorio"))
        self.SetSize((420, 620))

        self.panel = wx.Panel(self)
        self._create_interface()
        self._setup_accelerators()
        self.Bind(wx.EVT_CLOSE, self.close)

        if reminder_to_edit is None:
            self.date_picker.SetValue(wx.DateTime.Now())

        self._load_sound_config()

        if reminder_to_edit is not None:
            self._populate_from_reminder(reminder_to_edit[1])

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

        # Translators: Etiqueta para el campo de pre-notificación (avisar X minutos antes).
        sizer.Add(wx.StaticText(self.panel, label=_("Avisar X minutos antes (vac&ío para no usar):")), 0, wx.ALL | wx.EXPAND, 5)
        self.pre_notification_field = wx.TextCtrl(self.panel)
        sizer.Add(self.pre_notification_field, 0, wx.ALL | wx.EXPAND, 5)

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

        if self._edit_target is not None:
            # Translators: Botón para guardar los cambios al editar un recordatorio.
            submit_label = _("&Guardar cambios")
        else:
            # Translators: Botón para añadir el recordatorio.
            submit_label = _("&Agregar Recordatorio")
        self.submit_button = wx.Button(self.panel, label=submit_label)
        sizer.Add(self.submit_button, 0, wx.ALL | wx.CENTER, 5)
        self.submit_button.Bind(wx.EVT_BUTTON, self._on_submit)

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

    # --- Rellenado de campos en modo edición ---

    def _populate_from_reminder(self, reminder):
        """Pre-rellena el formulario con los valores actuales del recordatorio."""
        # Mensaje.
        self.message_field.SetValue(reminder.get("message", ""))

        # Tareas, una por línea.
        tasks = reminder.get("tasks") or []
        if tasks:
            self.tasks_field.SetValue("\n".join(t.get("description", "") for t in tasks))

        # Fecha y hora.
        reminder_time = reminder["time"]
        wx_date = wx.DateTime()
        # wx.DateTime usa meses indexados en 0.
        wx_date.Set(reminder_time.day, reminder_time.month - 1, reminder_time.year)
        self.date_picker.SetValue(wx_date)
        self.specific_date_check.SetValue(True)
        self.date_picker.Show()
        self.date_label.Show()
        self.hours_field.SetSelection(reminder_time.hour)
        self.minutes_field.SetSelection(reminder_time.minute)

        # Pre-notificación.
        pre_min = reminder.get("pre_notification_minutes")
        if pre_min:
            self.pre_notification_field.SetValue(str(pre_min))

        # Recurrencia.
        recurrence = reminder.get("recurrence")
        custom_interval = reminder.get("custom_interval")
        if recurrence in RECURRENCE_KEYS or custom_interval:
            self.recurrence_check.SetValue(True)
            self.recurrence_choice.Show()
            self.recurrence_label.Show()
            if recurrence in RECURRENCE_KEYS:
                self.recurrence_choice.SetSelection(RECURRENCE_KEYS.index(recurrence))
            elif custom_interval:
                self.recurrence_choice.SetSelection(RECURRENCE_KEYS.index(RECURRENCE_CUSTOM))
            if custom_interval:
                self.custom_interval_field.SetValue(str(custom_interval))
                self.custom_interval_field.Show()
                self.custom_interval_label.Show()

        # Sonido personalizado.
        sound_file = reminder.get("sound_file")
        if sound_file and os.path.exists(sound_file):
            self.custom_sound_check.SetValue(True)
            self.select_folder_btn.Show()
            self.play_button.Show()
            self.sound_choice.Show()
            self.select_sound_label.Show()
            # Si el archivo viene de una carpeta distinta a la guardada, cargarla.
            folder = os.path.dirname(sound_file)
            if folder and folder != self.sound_folder:
                self.sound_folder = folder
                self._load_sounds_from_folder()
            basename = os.path.basename(sound_file)
            if basename in self.sound_choice.GetItems():
                self.sound_choice.SetStringSelection(basename)
            self.selected_sound = sound_file

        self.panel.Layout()

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

    def _on_submit(self, event):
        # --- Validación de intervalo personalizado ---
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

        # --- Validación de pre-notificación ---
        pre_notification_minutes = None
        raw_pre = self.pre_notification_field.GetValue().strip()
        if raw_pre:
            try:
                pre_notification_minutes = int(raw_pre)
                if pre_notification_minutes <= 0:
                    raise ValueError
            except ValueError:
                # Translators: Error: el pre-aviso debe ser entero positivo.
                wx.MessageBox(_("El pre-aviso debe ser un número entero positivo de minutos."), _("Error"), wx.ICON_ERROR)
                self.pre_notification_field.SetFocus()
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

        if self.custom_sound_check.IsChecked() and self.sound_choice.GetValue() and self.sound_folder:
            self.selected_sound = os.path.join(self.sound_folder, self.sound_choice.GetValue())
        else:
            self.selected_sound = None

        # --- Diferenciar añadir vs editar ---
        if self._edit_target is not None:
            reminder_id, original = self._edit_target
            # Si cambia el mensaje, verificar duplicados contra los demás.
            if message.lower() != original["message"].lower() and self.reminder_manager.has_duplicate_message(message, ignore_id=reminder_id):
                wx.MessageBox(_("Ya existe un recordatorio con el nombre '{}'").format(message), _("Error"), wx.ICON_ERROR)
                self.message_field.SetFocus()
                return

            updated = self.reminder_manager.update_reminder(
                reminder_id,
                message=message,
                time=reminder_time,
                recurrence=recurrence,
                sound_file=self.selected_sound,
                custom_interval=custom_interval,
                tasks=tasks,
                pre_notification_minutes=pre_notification_minutes,
            )
            if updated:
                gui.messageBox(REMINDER_UPDATED_MESSAGE.format(message), REMINDER_UPDATED_TITLE)
                self.Destroy()
            else:
                # Translators: Error genérico al actualizar un recordatorio.
                wx.MessageBox(_("No se pudo actualizar el recordatorio."), _("Error"), wx.ICON_ERROR)
            return

        # Modo "añadir".
        self.reminder_manager.add_reminder(
            message, reminder_time, recurrence,
            self.selected_sound, custom_interval, tasks,
            pre_notification_minutes=pre_notification_minutes,
        )
        self.message_field.Clear()
        self.tasks_field.Clear()
        self.pre_notification_field.Clear()
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
