# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU.
# Consulte el archivo COPYING.txt para obtener más detalles.

"""Primitivas OAuth 2.0 con PKCE para Google Calendar.

Este módulo no almacena tokens. La integración de interfaz y un almacén seguro
de credenciales se añadirán después; mantener los tokens fuera de la
configuración de NVDA evita que se persistan como texto legible.
"""

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .google_calendar_config import GOOGLE_CALENDAR_CLIENT_ID
from .google_calendar_credentials import GoogleCalendarClientSecretStore


AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
REVOCATION_ENDPOINT = "https://oauth2.googleapis.com/revoke"
DEFAULT_SCOPES = ("https://www.googleapis.com/auth/calendar.events.owned",)


class GoogleCalendarOAuthError(RuntimeError):
    """Indica que Google rechazó o no pudo completar una operación OAuth."""


@dataclass(frozen=True)
class AuthorizationRequest:
    """Datos efímeros que deben conservarse hasta recibir la redirección OAuth."""

    url: str
    state: str
    code_verifier: str


class GoogleCalendarOAuthClient:
    """Crea solicitudes PKCE y canjea códigos del cliente de escritorio."""

    def __init__(self, client_id=GOOGLE_CALENDAR_CLIENT_ID, client_secret=None, credential_store=None, opener=urlopen):
        self.client_id = client_id
        self.client_secret = client_secret
        self.credential_store = credential_store or GoogleCalendarClientSecretStore()
        self._opener = opener

    def create_authorization_request(self, redirect_uri, scopes=DEFAULT_SCOPES):
        """Devuelve una URL de consentimiento y los valores PKCE asociados."""
        if not redirect_uri.startswith(("http://127.0.0.1:", "http://localhost:")):
            raise ValueError("La redirección OAuth debe usar un servidor local de bucle.")
        if not scopes:
            raise ValueError("Se requiere al menos un permiso de Google Calendar.")

        code_verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        state = secrets.token_urlsafe(32)
        query = urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        })
        return AuthorizationRequest(
            url="{}?{}".format(AUTHORIZATION_ENDPOINT, query),
            state=state,
            code_verifier=code_verifier,
        )

    @staticmethod
    def validate_state(expected_state, returned_state):
        """Comprueba el estado de OAuth con comparación de tiempo constante."""
        if not returned_state or not hmac.compare_digest(expected_state, returned_state):
            raise GoogleCalendarOAuthError("La respuesta OAuth no coincide con la solicitud iniciada.")

    def exchange_code(self, code, redirect_uri, code_verifier):
        """Canjea un código de autorización por los tokens de Google."""
        if not code:
            raise ValueError("Google no devolvió un código de autorización.")
        return self._request_token({
            "client_id": self.client_id,
            "client_secret": self._client_secret(),
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        })

    def refresh_access_token(self, refresh_token):
        """Renueva un token de acceso sin volver a mostrar el consentimiento."""
        if not refresh_token:
            raise ValueError("No hay token de actualización disponible.")
        return self._request_token({
            "client_id": self.client_id,
            "client_secret": self._client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })

    def _client_secret(self):
        secret = self.client_secret or self.credential_store.load()
        if not secret:
            raise GoogleCalendarOAuthError(
                "Falta la credencial privada de Google Calendar en el perfil de NVDA."
            )
        return secret

    def revoke_token(self, token):
        """Revoca el token remoto antes de borrar su copia local."""
        if not token:
            raise ValueError("No hay token para revocar.")
        request = Request(
            REVOCATION_ENDPOINT,
            data=urlencode({"token": token}).encode("ascii"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with self._opener(request, timeout=15):
                pass
        except HTTPError as error:
            raise GoogleCalendarOAuthError("Google no pudo revocar la autorización: {}".format(error.code)) from error
        except Exception as error:
            raise GoogleCalendarOAuthError("No se pudo contactar el servicio de autorización de Google.") from error

    def _request_token(self, parameters):
        body = urlencode(parameters).encode("ascii")
        request = Request(
            TOKEN_ENDPOINT,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with self._opener(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            try:
                payload = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            detail = payload.get("error_description", payload.get("error", str(error.code)))
            raise GoogleCalendarOAuthError("Google rechazó la autorización: {}".format(detail)) from error
        except Exception as error:
            raise GoogleCalendarOAuthError("No se pudo contactar el servicio de autorización de Google.") from error
        if not isinstance(payload, dict) or payload.get("error"):
            detail = payload.get("error_description", payload.get("error", "respuesta no válida")) if isinstance(payload, dict) else "respuesta no válida"
            raise GoogleCalendarOAuthError("Google rechazó la autorización: {}".format(detail))
        if not payload.get("access_token"):
            raise GoogleCalendarOAuthError("Google no devolvió un token de acceso.")
        return payload
