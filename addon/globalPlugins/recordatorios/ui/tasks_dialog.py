# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

"""Diálogo para marcar/desmarcar las tareas de un recordatorio como completadas."""

import wx

import addonHandler

addonHandler.initTranslation()


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
