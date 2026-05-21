# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Punto de entrada del complemento. Registra `GlobalPlugin` y conecta las acciones del menú."""

from datetime import datetime

import wx

import addonHandler
import config
import globalPluginHandler
import globalVars
import gui
import scriptHandler
import ui
from gui import settingsDialogs

addonHandler.initTranslation()

from .constants import (
    DELETE_REMINDER_MESSAGE,
    DELETE_REMINDER_TITLE,
    MANAGE_TASKS_MESSAGE,
    MANAGE_TASKS_TITLE,
    NO_REMINDERS_TO_RESCHEDULE_MESSAGE,
    NO_REMINDERS_WITH_TASKS_MESSAGE,
    REMINDER_DELETED_MESSAGE,
    REMINDER_DELETED_TITLE,
    REMINDER_RESCHEDULED_MESSAGE,
    REMINDER_RESCHEDULED_TITLE,
    RESCHEDULE_REMINDER_MESSAGE,
    RESCHEDULE_REMINDER_TITLE,
    TASK_COMPLETED_STATUS,
    TASK_PENDING_STATUS,
    UPDATE_TASKS_MESSAGE,
)
from .manager import ReminderManager
from .recurrence import RECURRENCE_KEYS, recurrence_labels
from .ui.config_panel import remindersConfigPanel
from .ui.reminder_app import ReminderApp
from .ui.reschedule_dialog import RescheduleReminderDialog
from .ui.tasks_dialog import ManageTasksDialog


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
