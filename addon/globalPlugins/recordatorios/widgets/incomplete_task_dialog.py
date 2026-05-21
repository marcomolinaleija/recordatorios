# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Diálogo mostrado cuando un recordatorio con tareas pendientes llega a su hora."""

import wx

import addonHandler

addonHandler.initTranslation()

from ..constants import ID_DELETE, ID_REVIEW_SNOOZE, ID_SNOOZE


class IncompleteTaskDialog(wx.Dialog):
    """Diálogo mostrado cuando un recordatorio con tareas pendientes llega a su hora."""

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
