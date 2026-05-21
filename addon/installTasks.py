# -*- coding: utf-8 -*-

# Este archivo está cubierto por la Licencia Pública General de GNU.
# Última actualización 2024
# Derechos de autor (C) 2024 Marco Leija <marcoleija@marco-ml.com>

import addonHandler

addonHandler.initTranslation()


DONATION_URL = "https://paypal.me/paymentToMl"


def _open_donation_page():
    import webbrowser
    webbrowser.open(DONATION_URL)


def _request_donation():
    import wx
    import gui

    # Translators: The title of the dialog requesting donations from users.
    title = _("Por favor, dona")
    # Translators: The text of the donate dialog.
    message = _("""Recordatorios  - complemento gratuito para NVDA.
Puedes hacer una donación a Marco Leija para ayudar en el desarrollo futuro de este complemento.
¿Quieres hacer una donación ahora? Para la transacción, serás redirigido al sitio web de PayPal.""")

    if gui.messageBox(message, title, style=wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
        _open_donation_page()
        return True
    return False


def onInstall():
    import globalVars
    # No solicitar la donación cuando NVDA está en modo seguro (p. ej. pantalla de inicio de sesión).
    if not globalVars.appArgs.secure:
        _request_donation()
