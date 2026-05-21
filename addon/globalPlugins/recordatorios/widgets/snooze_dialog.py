# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Diálogo para elegir cuántos minutos posponer un recordatorio."""

import wx

import addonHandler

addonHandler.initTranslation()

from ..constants import DEFAULT_SNOOZE_MINUTES


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
