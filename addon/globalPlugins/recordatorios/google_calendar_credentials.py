"""Lectura de la credencial OAuth privada del perfil de NVDA."""

import json
import os

import globalVars


class GoogleCalendarClientSecretStore:
    """Obtiene el secreto desde un archivo fuera del código y del complemento."""

    file_name = "recordatorios-google-oauth.json"

    def __init__(self, path=None):
        self.path = path or os.path.join(globalVars.appArgs.configPath, self.file_name)

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as credential_file:
                credentials = json.load(credential_file)
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        secret = credentials.get("client_secret") if isinstance(credentials, dict) else None
        return secret if isinstance(secret, str) and secret else None
