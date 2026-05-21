# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Panel de configuración del complemento en el diálogo de Opciones de NVDA."""

import wx

import addonHandler
import config
import gui
from gui import settingsDialogs

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

    def onSave(self):
        config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"] = int(
            self.numberOfTimesToNotifyReminder.GetStringSelection()
        )
        config.conf["remindersConfig"]["notificationInterval"] = int(
            self.notificationInterval.GetStringSelection()
        )
