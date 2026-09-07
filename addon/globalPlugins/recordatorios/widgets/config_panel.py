# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Panel de configuración del complemento en el diálogo de Opciones de NVDA."""

import wx
import threading

import addonHandler
import config
import gui
from gui import settingsDialogs

from ..google_calendar_authorization import GoogleCalendarAuthorizer, GoogleCalendarTokenStore
from ..google_calendar_export import GoogleCalendarExporter

addonHandler.initTranslation()


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

        helper.addItem(wx.StaticText(self, label=_("Google Calendar")))
        self.google_status = helper.addItem(wx.StaticText(self, label=self._google_status_text()))
        self.google_connect = helper.addItem(wx.Button(self, label=_("Conectar con Google Calendar")))
        self.google_connect.Bind(wx.EVT_BUTTON, self._connect_google_calendar)
        self.google_export = helper.addItem(wx.Button(self, label=_("Exportar recordatorios ahora")))
        self.google_export.Bind(wx.EVT_BUTTON, self._export_google_calendar)

    def _google_status_text(self):
        return _("Google Calendar conectado.") if GoogleCalendarTokenStore().load() else _("Google Calendar no está conectado.")

    def _connect_google_calendar(self, event):
        self.google_connect.Disable()
        authorizer = GoogleCalendarAuthorizer()
        try:
            authorizer.start(self._google_connected, self._google_connection_failed)
        except Exception as error:
            self._google_connection_failed(error)

    def _google_connected(self):
        wx.CallAfter(self._finish_google_connection, _("Google Calendar conectado correctamente."))

    def _google_connection_failed(self, error):
        wx.CallAfter(self._finish_google_connection, _("No se pudo conectar con Google Calendar: {}").format(error))

    def _finish_google_connection(self, message):
        self.google_status.SetLabel(message)
        self.google_connect.Enable()

    def _export_google_calendar(self, event):
        manager = getattr(type(self), "reminder_manager", None)
        if manager is None:
            self._finish_google_export(_("No se pudo acceder a los recordatorios para exportarlos."))
            return
        self.google_export.Disable()
        threading.Thread(target=self._export_in_background, args=(manager,), daemon=True).start()

    def _export_in_background(self, manager):
        try:
            reminders = manager.snapshot()
            GoogleCalendarExporter().export(reminders, lambda reminder_id, event_id: manager.update_reminder(reminder_id, google_event_id=event_id))
            message = _("Se exportaron {} recordatorios a Google Calendar.").format(len(reminders))
        except Exception as error:
            message = _("No se pudieron exportar los recordatorios: {}").format(error)
        wx.CallAfter(self._finish_google_export, message)

    def _finish_google_export(self, message):
        self.google_status.SetLabel(message)
        self.google_export.Enable()

    def onSave(self):
        config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"] = int(
            self.numberOfTimesToNotifyReminder.GetStringSelection()
        )
        config.conf["remindersConfig"]["notificationInterval"] = int(
            self.notificationInterval.GetStringSelection()
        )
