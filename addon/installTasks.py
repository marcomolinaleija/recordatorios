# -*- coding: utf-8 -*-

# Este archivo está cubierto por la Licencia Pública General de GNU.
# Última actualización 2024
# Derechos de autor (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>

import addonHandler

addonHandler.initTranslation()

class donate:
    def open():
        import webbrowser
        webbrowser.open(f"https://paypal.me/paymentToMl")

    def request():
        import wx
        import gui
        
        # Translators: The title of the dialog requesting donations from users.
        title ="Por favor, dona"
        
        # Translators: The text of the donate dialog
        message = """Recordatorios  - complemento gratuito para NVDA.
        Puedes hacer una donación a Marco Leija para ayudar en el desarrollo futuro de este complemento.
        ¿Quieres hacer una donación ahora? Para la transacción, serás redirigido al sitio web de PayPal."""
        
        name = addonHandler.getCodeAddon().manifest['summary']
        if gui.messageBox(message.format(name=name), title, style=wx.YES_NO|wx.ICON_QUESTION) == wx.YES:
            donate.open()
            return True
        return False

def onInstall():
    import globalVars
    # This checks if NVDA is running in a secure mode (e.g., on the Windows login screen),
    # which would prevent the addon from performing certain actions.
    if not globalVars.appArgs.secure:
        donate.request()