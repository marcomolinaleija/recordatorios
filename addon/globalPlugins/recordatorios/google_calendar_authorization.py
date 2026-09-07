"""Autorización local y almacenamiento protegido para Google Calendar."""

import base64
import ctypes
import json
import os
import socket
import threading
import webbrowser
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

import globalVars

from .google_calendar import GoogleCalendarOAuthClient, GoogleCalendarOAuthError


class GoogleCalendarTokenStore:

	"""Guarda los tokens cifrados con DPAPI, ligados al perfil de Windows."""

	def __init__(self, path=None):
		self.path = path or os.path.join(globalVars.appArgs.configPath, "recordatorios-google-calendar.dat")

	def save(self, tokens):
		if os.name != "nt":
			raise RuntimeError("El almacenamiento protegido sólo está disponible en Windows.")
		payload = json.dumps(tokens, ensure_ascii=False).encode("utf-8")
		encrypted = self._protect(payload)
		with open(self.path, "wb") as token_file:
			token_file.write(base64.b64encode(encrypted))

	def load(self):
		if not os.path.exists(self.path):
			return None
		try:
			with open(self.path, "rb") as token_file:
				payload = base64.b64decode(token_file.read())
			return json.loads(self._unprotect(payload).decode("utf-8"))
		except (OSError, ValueError, json.JSONDecodeError):
			return None

	def delete(self):
		try:
			os.unlink(self.path)
		except FileNotFoundError:
			pass

	@staticmethod
	def _crypt(data, protect):
		class DataBlob(ctypes.Structure):
			_fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte)))

		buffer = ctypes.create_string_buffer(data)
		input_blob = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
		output_blob = DataBlob()
		crypt32 = ctypes.windll.crypt32
		if protect:
			success = crypt32.CryptProtectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
		else:
			success = crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
		if not success:
			raise ctypes.WinError()
		try:
			return ctypes.string_at(output_blob.pbData, output_blob.cbData)
		finally:
			ctypes.windll.kernel32.LocalFree(output_blob.pbData)

	def _protect(self, data):
		return self._crypt(data, True)

	def _unprotect(self, data):
		return self._crypt(data, False)


class GoogleCalendarAuthorizer:
	"""Ejecuta OAuth con PKCE usando sólo un retorno local de un uso."""

	def __init__(self, token_store=None, oauth_client=None, browser_opener=webbrowser.open):
		self.token_store = token_store or GoogleCalendarTokenStore()
		self.oauth_client = oauth_client or GoogleCalendarOAuthClient()
		self.browser_opener = browser_opener

	def start(self, on_success, on_error):
		server = self._create_server()
		redirect_uri = "http://127.0.0.1:{}/callback".format(server.server_port)
		authorization = self.oauth_client.create_authorization_request(redirect_uri)
		threading.Thread(
			target=self._serve_once,
			args=(server, authorization, redirect_uri, on_success, on_error),
			daemon=True,
		).start()
		if not self.browser_opener(authorization.url):
			raise GoogleCalendarOAuthError("No se pudo abrir el navegador para autorizar Google Calendar.")

	@staticmethod
	def _create_server():
		class CallbackServer(HTTPServer):
			allow_reuse_address = True

		class CallbackHandler(BaseHTTPRequestHandler):
			def do_GET(self):
				self.server.callback_query = parse_qs(urlsplit(self.path).query)
				body = "<html><body><h1>Autorización recibida</h1><p>Ya puedes volver a NVDA.</p></body></html>"
				self.send_response(200)
				self.send_header("Content-Type", "text/html; charset=utf-8")
				self.send_header("Content-Length", str(len(body.encode("utf-8"))))
				self.end_headers()
				self.wfile.write(body.encode("utf-8"))

			def log_message(self, *args):
				pass

		return CallbackServer(("127.0.0.1", 0), CallbackHandler)

	def _serve_once(self, server, authorization, redirect_uri, on_success, on_error):
		server.timeout = 300
		try:
			server.handle_request()
			query = getattr(server, "callback_query", {})
			if query.get("error"):
				raise GoogleCalendarOAuthError("Google canceló la autorización: {}".format(query["error"][0]))
			self.oauth_client.validate_state(authorization.state, query.get("state", [None])[0])
			tokens = self.oauth_client.exchange_code(query.get("code", [None])[0], redirect_uri, authorization.code_verifier)
			self.token_store.save(tokens)
			on_success()
		except Exception as error:
			on_error(error)
		finally:
			server.server_close()
