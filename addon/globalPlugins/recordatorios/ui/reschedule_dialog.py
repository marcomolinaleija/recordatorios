# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Diálogo para elegir la nueva fecha y hora de un recordatorio."""

import wx
import wx.adv

import addonHandler

addonHandler.initTranslation()


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
