"""Exportación unidireccional de Recordatorios a Google Calendar."""

import json
import threading
from datetime import timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .google_calendar import GoogleCalendarOAuthClient, GoogleCalendarOAuthError
from .google_calendar_authorization import GoogleCalendarTokenStore
from .recurrence import RECURRENCE_CUSTOM, RECURRENCE_DAILY, RECURRENCE_MONTHLY, RECURRENCE_WEEKLY


CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class GoogleCalendarExporter:
	"""Crea o actualiza eventos; nunca borra eventos de Google Calendar."""

	def __init__(self, token_store=None, oauth_client=None, opener=urlopen):
		self.token_store = token_store or GoogleCalendarTokenStore()
		self.oauth_client = oauth_client or GoogleCalendarOAuthClient()
		self.opener = opener

	def export(self, reminders, on_event):
		access_token = self._access_token()
		for reminder in reminders:
			event = self._upsert(access_token, reminder)
			on_event(reminder["id"], event["id"])

	def _access_token(self):
		tokens = self.token_store.load()
		if not tokens or not tokens.get("refresh_token"):
			raise GoogleCalendarOAuthError("Conecta Google Calendar antes de exportar.")
		refreshed = self.oauth_client.refresh_access_token(tokens["refresh_token"])
		refreshed["refresh_token"] = tokens["refresh_token"]
		self.token_store.save(refreshed)
		return refreshed["access_token"]

	def _upsert(self, access_token, reminder):
		payload = json.dumps(self._event_body(reminder)).encode("utf-8")
		event_id = reminder.get("google_event_id")
		method = "PATCH" if event_id else "POST"
		url = "{}/{}".format(CALENDAR_EVENTS_URL, event_id) if event_id else CALENDAR_EVENTS_URL
		try:
			return self._request(url, method, payload, access_token)
		except HTTPError as error:
			if event_id and error.code == 404:
				return self._request(CALENDAR_EVENTS_URL, "POST", payload, access_token)
			raise GoogleCalendarOAuthError("Google Calendar rechazó la exportación: {}".format(error.code)) from error

	def _request(self, url, method, payload, access_token):
		request = Request(url, data=payload, method=method, headers={
			"Authorization": "Bearer {}".format(access_token),
			"Content-Type": "application/json",
		})
		try:
			with self.opener(request, timeout=20) as response:
				return json.loads(response.read().decode("utf-8"))
		except GoogleCalendarOAuthError:
			raise
		except Exception as error:
			raise GoogleCalendarOAuthError("No se pudo contactar Google Calendar.") from error

	@staticmethod
	def _event_body(reminder):
		start = reminder["time"]
		body = {
			"summary": reminder["message"],
			"description": "Creado por Recordatorios para NVDA.",
			"start": {"dateTime": start.isoformat()},
			"end": {"dateTime": (start + timedelta(minutes=30)).isoformat()},
			"extendedProperties": {"private": {"recordatoriosId": reminder["id"]}},
		}
		recurrence = GoogleCalendarExporter._recurrence_rule(reminder)
		if recurrence:
			body["recurrence"] = [recurrence]
		return body

	@staticmethod
	def _recurrence_rule(reminder):
		frequency = reminder.get("recurrence")
		if frequency == RECURRENCE_DAILY:
			return "RRULE:FREQ=DAILY"
		if frequency == RECURRENCE_WEEKLY:
			return "RRULE:FREQ=WEEKLY"
		if frequency == RECURRENCE_MONTHLY:
			return "RRULE:FREQ=MONTHLY"
		if frequency == RECURRENCE_CUSTOM and reminder.get("custom_interval"):
			return "RRULE:FREQ=MINUTELY;INTERVAL={}".format(reminder["custom_interval"])
		return None
