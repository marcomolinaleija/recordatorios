# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>


import wx
import wx.adv
import threading
import time
import json
import os
import addonHandler
addonHandler.initTranslation()

from datetime import datetime, timedelta

import tones
import ui
import gui
import globalPluginHandler
import scriptHandler
import config
import globalVars
from gui import settingsDialogs
from nvwave import playWaveFile
# Variables "constantes" para evitar errores
DELETE_REMINDER_MESSAGE = _("Selecciona el recordatorio que deseas eliminar:")
DELETE_REMINDER_TITLE = _("Eliminar recordatorio")
REMINDER_DELETED_MESSAGE = _("El recordatorio '{}' ha sido eliminado.")
REMINDER_DELETED_TITLE = _("Recordatorio eliminado")

class ReminderManager:
	"""
	Clase que maneja los recordatorios y su verificación en segundo plano.
	"""
	
	def __init__(self):
		# Lista para almacenar los recordatorios añadidos
		self.reminders = []
		# Variable booleana para controlar si el hilo de verificación sigue corriendo
		self.running = True
		# Archivo para guardar y cargar los recordatorios
		self.file_path = os.path.join(globalVars.appArgs.configPath, "recordatorios.json")
		# Cargamos los recordatorios
		self.load_reminders()

		# Creamos el hilo para la verificación de los recordatorios en segundo plano.
		verifier_thread = threading.Thread(target=self.check_reminders, daemon=True)
		# Iniciamos el hilo previamente creado
		verifier_thread.start()
	def add_reminder(self, message, reminder_time, recurrence=None, sound_file=None, custom_interval=None):
		"""
		Método que añade un recordatorio, verificando si no existe otro con el mismo nombre
		Args:
			message (str): El mensaje del recordatorio.
			reminder_time (datetime): La hora en la que llegará el recordatorio.
			recurrence (str): La frecuencia del recordatorio. diario, semanal, mensual, si aplica.
			sound_file (str): ruta con el sonido para el recordatorio
			custom_interval (int): Tiempo personalizado para la notificación del recordatorio
		"""
	
		# Convertimos el mensaje a minúsculas para la comparación
		message_lower = message.lower()
		# Verificamos si ya existe un recordatorio con el mismo nombre
		if any(existing_message.lower() == message_lower for existing_message, *_ in self.reminders):
			ui.message(_("Ya existe un recordatorio con el nombre '{}'").format(message))
			return

		# en caso contrario, se añade el recordatorio y se notifica mediante ui.message
		self.reminders.append((message, reminder_time, recurrence, sound_file, custom_interval))
	
		# Verificar si el recordatorio es para hoy o para una fecha futura
		now = datetime.now()
		if reminder_time.date() == now.date():
			# Si es para hoy, mostramos solo la hora
			translated_message_reminder = _("Recordatorio agregado para {time}")
			ui.message(translated_message_reminder.format(time=reminder_time.strftime('%H:%M')))
		else:
			# Si es para una fecha futura, mostramos fecha y hora
			translated_message_reminder = _("Recordatorio agregado para el {date} a las {time}")
			ui.message(translated_message_reminder.format(
				date=reminder_time.strftime('%d/%m/%Y'),
				time=reminder_time.strftime('%H:%M')
			))

		# llamamos al método para guardar los recordatorios
		self.save_reminders()

	def check_reminders(self):
		"""
		Método que verifica periódicamente si hay recordatorios que deben ser notificados.
		"""
		while self.running:
			now = datetime.now()
			for i, reminder in enumerate(self.reminders):
				message, reminder_time, recurrence, sound_file, custom_interval = reminder
			
				if reminder_time <= now:
					# Notificar al usuario
					self.notify(message, sound_file)

					# Reprogramar el recordatorio según la recurrencia
					if custom_interval:
						reminder_time += timedelta(minutes=custom_interval)
					elif recurrence == "diario":
						reminder_time += timedelta(days=1)
					elif recurrence == "semanal":
						reminder_time += timedelta(weeks=1)
					elif recurrence == "mensual":
						reminder_time = self.add_month(reminder_time)
					else:
						# Si no es recurrente, eliminar el recordatorio y continuar
						self.reminders.pop(i)
						self.save_reminders()
						continue

					# Actualizar el recordatorio en la lista
					self.reminders[i] = (message, reminder_time, recurrence, sound_file, custom_interval)
					self.save_reminders()

			# Verificar recordatorios cada segundo
			time.sleep(1)


	def add_month(self, date):
		"""
		Método que añade un mes a la fecha proporcionada.
		Este método maneja la transición de meses y años correctamente. Si el mes actual es
		diciembre, se reinicia al mes de enero del siguiente año. Se utiliza el método 
		replace de datetime para devolver una nueva fecha con el mes y el año 
		actualizados.
		Args:
			date (datetime): La fecha a la que se le añadirá un mes.
		Returns:
			datetime: Una nueva fecha con un mes añadido.
			"""

		# Determinamos el siguiente mes. si el mes actual es diciembre, reiniciamos a enero.
		month = date.month + 1 if date.month < 12 else 1
		# Si el mes actual es diciembre, incrementamos el año en 1, de lo contrario, mantenemos el año actual.
		year = date.year if date.month < 12 else date.year + 1
		# Retornamos una nueva fecha con el mes y el año actualizados.
		return date.replace(month=month, year=year)

	def notify(self, message, sound_file=None):
		"""
		Método que envía la notificación cuando llega la hora del recordatorio
		Args:
			message (str): el mensaje que se mostrará al usuario
			sound_file (str): Ruta al sonido personalizado, si se seleccionó
		"""
		# Obtenemos el valor de notificationInterval como entero desde remindersConfig
		self.interval = int(config.conf["remindersConfig"]["notificationInterval"])
		# Ahora obtenemos el número de veces que se reproducirá la notificación del recordatorio
		num_times = int(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"])
		# bucle que toma como rango el número de notificaciones
		for i in range(num_times):
			# si hay un sonido seleccionado para el recordatorio y si el archivo existe, continúa con el bloque de instrucciones.
			ui.message(_("Recordatorio: {}").format(message))
			if sound_file and os.path.exists(sound_file):
				# Reproducir el sonido personalizado usando nvwave
				playWaveFile(sound_file)
			# Si el sonido no existe o el usuario no seleccionó alguno, entonces reproduce un beep desde el módulo tones de NVDA.
			else:
				# Reproducir sonido para la notificación
				tones.beep(440, 500)
			# Evitar notificaciones simultáneas
			if i < num_times - 1:
				time.sleep(self.interval)

	def stop(self):
		"""
		Método que detiene el hilo de  verificación de los recordatorios
		"""
		# Se cambia el estado de running a False para detener la verificación
		self.running = False

	def save_reminders(self):
		"""
		Método para guardar los recordatorios en un archivo .json
		"""
		# Abrimos el archivo file_path en modo escritura ('w')
		with open(self.file_path, 'w') as file:
			# Creamos una lista de los recordatorios formateando la hora para almacenarlos
			reminders_data = [(msg, time.strftime('%Y-%m-%d %H:%M'), rec, sound_file, custom_interval) for msg, time, rec, sound_file, custom_interval in self.reminders]
			# Escribimos la lista de los recordatorios en el archivo con formato json
			json.dump(reminders_data, file)

	def load_reminders(self):
		"""
		Método para cargar los recordatorios desde el archivo json
		"""
		# Verificamos si el archivo existe antes de cargarlo
		if os.path.exists(self.file_path):
			# Si existe, lo abrimos en modo lectura ('r')
			with open(self.file_path, 'r') as file:
				# Cargamos los datos del archivo en la variable reminders_data como json
				reminders_data = json.load(file)
				# Convertimos los datos cargados a la estructura de recordatorios,  convirtiendo el tiempo de cadena a un objeto datetime.
				self.reminders = [(msg, datetime.strptime(time, '%Y-%m-%d %H:%M'), rec, sound_file, custom_interval) for msg, time, rec, sound_file, custom_interval in reminders_data]



class ReminderApp(wx.Frame):
	"""
	Clase que contiene la interfaz para añadir un nuevo recordatorio.
	Hereda de wx.frame.
	"""
	
	def __init__(self, *args, **kw):
		super(ReminderApp, self).__init__(*args, **kw)
		# Configuramos el título de la ventana y el tamaño de la misma
		self.SetTitle(_("Añadir recordatorio"))
		self.SetSize((400, 400))
		# Variables para el sonido personalizado
		self.sound_folder = None
		self.selected_sound = None
		
		# Creamos el panel que contendrá los elementos de la interfaz
		self.panel = wx.Panel(self)
		# Llamado al método para crear la interfaz.
		self.create_interface()
		# Configuración de los atajos con accelerators
		self.setup_accelerators()
		self.reminder_manager = reminder_manager
		# evento para salir de la interfaz.
		self.Bind(wx.EVT_CLOSE, self.close)
		# Inicializar DatePickerCtrl con la fecha actual
		today = wx.DateTime.Now()
		self.date_picker.SetValue(today)


		# Cargar la configuración de sonidos
		self.load_sound_config()

	def save_sound_config(self):
		"""
		Guarda la carpeta de sonidos y el archivo seleccionado en el JSON.
		"""
		config_path = os.path.join(globalVars.appArgs.configPath, "sonidos_recordatorios.json")
		with open(config_path, 'w') as file:
			config_data = {
				"sound_folder": self.sound_folder,
				"selected_sound": self.selected_sound
			}
			json.dump(config_data, file)

	def load_sound_config(self):
		"""
		Carga la configuración de sonidos (carpeta y archivo) desde el JSON.
		"""
		config_path = os.path.join(globalVars.appArgs.configPath, "sonidos_recordatorios.json")
		if os.path.exists(config_path):
			with open(config_path, 'r') as file:
				config_data = json.load(file)
				self.sound_folder = config_data.get("sound_folder")
				self.selected_sound = config_data.get("selected_sound")
				# Si ya hay una carpeta y un sonido cargado, los mostramos en la interfaz
				if self.sound_folder and os.path.exists(self.sound_folder):
					self.load_sounds_from_folder()
					if self.selected_sound:
						# Selecciona el sonido previamente guardado en el ComboBox
						sound_file = os.path.basename(self.selected_sound)
						if sound_file in self.sound_choice.GetItems():
							self.sound_choice.SetStringSelection(sound_file)
				else:
					self.sound_folder = None
					self.selected_sound = None
					self.save_sound_config()

	def create_interface(self):
		"""
		Método que contiene todos los elementos para la interfaz.
		"""
		# Creamos el sizer, vertical.
		sizer = wx.BoxSizer(wx.VERTICAL)
		# Etiqueta y cuadro para el mensaje del recordatorio
		#Translators: Etiqueta que indica al usuario que escriba el mensaje para el recordatorio, mensaje a ser mostrado en la notificación.
		message_label = wx.StaticText(self.panel, label=_("&Mensaje del Recordatorio:"))
		sizer.Add(message_label, 0, wx.ALL | wx.EXPAND, 5)

		self.message_field = wx.TextCtrl(self.panel)
		sizer.Add(self.message_field, 0, wx.ALL | wx.EXPAND, 5)
		# Nueva casilla para seleccionar si usar fecha específica
		#Translators: Casilla que pregunta al usuario si desea usar una fecha específica
		self.specific_date_check = wx.CheckBox(self.panel, label=_("&Usar fecha específica"))
		sizer.Add(self.specific_date_check, 0, wx.ALL | wx.EXPAND, 5)
		self.specific_date_check.Bind(wx.EVT_CHECKBOX, self.toggle_specific_date)

		# Contenedor para selector de fecha
		#Translators: Etiqueta para el selector de fecha específica
		self.date_label = wx.StaticText(self.panel, label=_("Selecciona una fecha, utilizando flechas izquierda/derecha para moverse entre día, mes y año, y flechas arriba para modificar los valores:"))
		sizer.Add(self.date_label, 0, wx.ALL | wx.EXPAND, 5)
		# Ocultada por defecto
		self.date_label.Hide()
	
		# Usar DatePickerCtrl para seleccionar fecha
		self.date_picker = wx.adv.DatePickerCtrl(self.panel, style=wx.adv.DP_DROPDOWN | wx.adv.DP_SHOWCENTURY)
		sizer.Add(self.date_picker, 0, wx.ALL | wx.EXPAND, 5)
		# Ocultado por defecto
		self.date_picker.Hide()
		self.date_picker.Bind(wx.EVT_KEY_DOWN, self.on_date_key)
		self.date_picker.Bind(wx.adv.EVT_DATE_CHANGED, self.on_date_changed)
		# Mantener el seguimiento del componente actualmente seleccionado (día, mes, año)
		self.current_date_component = "día"  # Valores posibles: "día", "mes", "año"
		# Mantener la fecha anterior para detectar cambios
		self.previous_date = self.date_picker.GetValue()
		# Etiqueta y ComboBox para seleccionar la hora del recordatorio.
		#Translators: Etiqueta para indicar al usuario la selección de la hora, entre 00-23
		hours_label = wx.StaticText(self.panel, label=_("&Hora (formato 24h):"))
		sizer.Add(hours_label, 0, wx.ALL | wx.EXPAND, 5)
		self.hours_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(24)], style=wx.CB_DROPDOWN)
		sizer.Add(self.hours_field, 0, wx.ALL | wx.EXPAND, 5)
		#self.hours_field.SetSelection(0)

		# Etiqueta y ComboBox para la selección de los minutos
		#Translators: Etiqueta para indicar al usuario que seleccione un minuto, entre 00-59
		minutes_label = wx.StaticText(self.panel, label=_("&Minutos:"))
		sizer.Add(minutes_label, 0, wx.ALL | wx.EXPAND, 5)
		self.minutes_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(60)], style=wx.CB_DROPDOWN)
		sizer.Add(self.minutes_field, 0, wx.ALL | wx.EXPAND, 5)
		#self.minutes_field.SetSelection(0)

		# Etiqueta y casilla de verificación preguntando si el recordatorio será recurrente.
		#Translators: Casilla que pregunta al usuario si el recordatorio será recurrente.
		self.recurrence_check = wx.CheckBox(self.panel, label=_("&Recordatorio recurrente"))
		sizer.Add(self.recurrence_check, 0, wx.ALL | wx.EXPAND, 5)
		self.recurrence_check.Bind(wx.EVT_CHECKBOX, self.toggle_recurrence)

		# Etiqueta y ComboBox para seleccionar la recurrencia
		#Translators: Etiqueta que solicita al usuario seleccionar la recurrencia del recordatorio.
		self.recurrence_label = wx.StaticText(self.panel, label=_("Selecciona la frecuencia con la que llegará el recordatorio."))
		sizer.Add(self.recurrence_label, 0, wx.ALL | wx.EXPAND, 5)
		# Ocultada por defecto
		self.recurrence_label.Hide()
		#Translators: Cuadro convinado con las opciones para la recurrencia del recordatorio.
		self.recurrence_choice = wx.ComboBox(self.panel, choices=[_("diario"), _("semanal"), _("mensual"), _("Personalizado")], style=wx.CB_READONLY)
		sizer.Add(self.recurrence_choice, 0, wx.ALL | wx.EXPAND, 5)
		# Seleccionamos por defecto diario como recurrencia.
		self.recurrence_choice.SetSelection(0)
		self.recurrence_choice.Bind(wx.EVT_COMBOBOX, self.on_recurrence_selection)
		# Ocultamos el ComboBox por defecto.
		self.recurrence_choice.Hide()
		#Translators: Etiqueta que pregunta al usuario el intervalo para la recurrencia.
		self.custom_interval_label = wx.StaticText(self.panel, label=_("Intervalo de recurrencia personalizada (en minutos):"))
		sizer.Add(self.custom_interval_label, 0, wx.ALL | wx.EXPAND, 5)
		self.custom_interval_label.Hide()
		self.custom_interval_field = wx.TextCtrl(self.panel)
		sizer.Add(self.custom_interval_field, 0, wx.ALL | wx.EXPAND, 5)
		self.custom_interval_field.Hide()

		# Checkbox para habilitar sonido personalizado
		#Translators: Etiqueta que pregunta al usuario si desea utilizar un sonido personalizado para el recordatorio.
		self.custom_sound_check = wx.CheckBox(self.panel, label=_("&Usar sonido personalizado"))
		sizer.Add(self.custom_sound_check, 0, wx.ALL | wx.EXPAND, 5)
		# enlasar evento a la casilla.
		self.custom_sound_check.Bind(wx.EVT_CHECKBOX, self.toggle_custom_sound)
		# Etiqueta y comboBox para mostrar los sonidos en la carpeta seleccionada
		#Translators: Etiqueta que solicita al usuario seleccionar un sonido cargado en la lista.
		self.select_sound_label = wx.StaticText(self.panel, label=_("Selecciona un sonido de la lista."))
		sizer.Add(self.select_sound_label, 0, wx.ALL | wx.EXPAND, 5)
		# Se oculta por defecto.
		self.select_sound_label.Hide()
		self.sound_choice = wx.ComboBox(self.panel, choices=[], style= wx.CB_READONLY)
		sizer.Add(self.sound_choice, 0, wx.ALL | wx.EXPAND, 5)
		self.sound_choice.Hide()

		# Botón para reproducir el sonido seleccionado.
		#Translators: Botón para reproducir el sonido personalizado. se le indica al usuario que utilice la convinación ctrl+p como atajo de teclado.
		self.play_button = wx.Button(self.panel, label=_("Reproducir  ctrl+p"))
		sizer.Add(self.play_button, 0, wx.ALL | wx.CENTER, 5)
		self.play_button.Bind(wx.EVT_BUTTON, self.on_play_sound)
		# Ocultado por defecto.
		self.play_button.Hide()

		# Botón para seleccionar carpeta de sonidos
		#Translators: Botón para cargar una carpeta de sonidos. Se le indica al usuario que presione ctrl+f como atajo de teclado.
		self.select_folder_btn = wx.Button(self.panel, label=_("Seleccionar carpeta de sonidos  ctrl+f"))
		sizer.Add(self.select_folder_btn, 0, wx.ALL | wx.CENTER, 5)
		self.select_folder_btn.Bind(wx.EVT_BUTTON, self.on_select_folder)
		# Se oculta por defecto.
		self.select_folder_btn.Hide()

		# Botón para agregar el recordatorio.
		#Translators: Botón para guardar el recordatorio.
		add_button = wx.Button(self.panel, label=_("&Agregar Recordatorio"))
		sizer.Add(add_button, 0, wx.ALL | wx.CENTER, 5)
		add_button.Bind(wx.EVT_BUTTON, self.add_reminder)       
		
		# Botón de donación.
		#Translators: Botón que le indica al usuario que puede realizar una donación.
		donate_button = wx.Button(self.panel, label=_("&Donar al desarrollador del complemento"))
		sizer.Add(donate_button, 0, wx.ALL | wx.CENTER, 5)
		donate_button.Bind(wx.EVT_BUTTON, self.donate)
		# Botón para cancelar y cerrar la interfaz.
		#Translators: Este botón cancela y cierra la interfaz de recordatorios.
		cancel_button = wx.Button(self.panel, label=_("Salir  ctrl+q"))
		sizer.Add(cancel_button, 0, wx.ALL | wx.CENTER, 5)
		cancel_button.Bind(wx.EVT_BUTTON, self.close)

		self.panel.SetSizer(sizer)

	def toggle_specific_date(self, event):
		"""
		Método que alterna la visibilidad del selector de fecha en función de si está marcada la casilla.
		"""
		if self.specific_date_check.IsChecked():
			self.date_picker.Show()
			self.date_label.Show()
		else:
			self.date_picker.Hide()
			self.date_label.Hide()
		self.panel.Layout()

	def toggle_recurrence(self, event):
		"""
		Método que alterna la casilla recurrence para mostrar contenido en base a si está marcada o no.
		"""
		# Verificamos si la casilla de verificación está marcada.
		if self.recurrence_check.IsChecked():
			# Si es así, mostramos los elementos self.recurrence_choice y self.recurrence_label
			self.recurrence_choice.Show()
			self.recurrence_label.Show()
		else:
			# en caso contrario, solo los mantenemos ocultos.
			self.recurrence_choice.Hide()
			self.recurrence_label.Hide()
		# Actualizamos la interfaz.
		self.panel.Layout()

	def on_date_key(self, event):
		"""
		Maneja eventos de teclado en el selector de fecha para proporcionar retroalimentación verbal.
		"""
		key_code = event.GetKeyCode()
		date = self.date_picker.GetValue()
		
		# Detectar navegación entre día, mes y año (izquierda/derecha)
		if key_code == wx.WXK_LEFT:
			# Mover a la izquierda (por ejemplo, de mes a día)
			if self.current_date_component == "mes":
				self.current_date_component = "día"
				ui.message(_("Día: {}").format(date.GetDay()))
			elif self.current_date_component == "año":
				self.current_date_component = "mes"
				ui.message(_("Mes: {}").format(date.GetMonth() + 1))
		
		elif key_code == wx.WXK_RIGHT:
			# Mover a la derecha (por ejemplo, de día a mes)
			if self.current_date_component == "día":
				self.current_date_component = "mes"
				ui.message(_("Mes: {}").format(date.GetMonth() + 1))
			elif self.current_date_component == "mes":
				self.current_date_component = "año"
				ui.message(_("Año: {}").format(date.GetYear()))
		
		# Detectar cambios de valor (arriba/abajo) - el cambio real se manejará en on_date_changed
		elif key_code in (wx.WXK_UP, wx.WXK_DOWN):
			# Guardar la fecha actual para compararla después del evento
			self.previous_date = date
		
		# Procesar el evento normalmente
		event.Skip()

	def on_date_changed(self, event):
		"""
		Se llama cuando cambia la fecha, ya sea por teclado o por selección directa.
		Proporciona retroalimentación verbal sobre el cambio.
		"""
		# Obtener la nueva fecha
		new_date = self.date_picker.GetValue()
		old_date = self.previous_date
	
		# Comprobar qué componente ha cambiado
		if new_date.GetDay() != old_date.GetDay():
			ui.message(_("Día: {}").format(new_date.GetDay()))
			self.current_date_component = "día"
		elif new_date.GetMonth() != old_date.GetMonth():
			ui.message(_("Mes: {}").format(new_date.GetMonth() + 1))
			self.current_date_component = "mes"
		elif new_date.GetYear() != old_date.GetYear():
			ui.message(_("Año: {}").format(new_date.GetYear()))
			self.current_date_component = "año"
		
		# Actualizar la fecha anterior
		self.previous_date = new_date
		
		# Procesar el evento normalmente
		event.Skip()

	def on_recurrence_selection(self, event):
		selection = self.recurrence_choice.GetStringSelection()
		if selection == _("Personalizado"):
			self.custom_interval_field.Show()
			self.custom_interval_label.Show()
		else:
			self.custom_interval_field.Hide()
			self.custom_interval_label.Hide()
		self.panel.Layout()

	def toggle_custom_sound(self, event):
		"""
		al igual que el método anterior, alterna entre mostrar contenido si la casilla está marcada o no.
		"""
		# Si la casilla está marcada
		if self.custom_sound_check.IsChecked():
			"""
			Semuestran los siguientes elementos
			self.select_folder_btn,
			self.play_button,
			self.sound_choice,
			y self.select_sound_label
			"""
			
			self.select_folder_btn.Show()
			self.play_button.Show()
			self.sound_choice.Show()
			self.select_sound_label.Show()
		else:
			# En caso contrario, se mantienen ocultos los elementos.
			self.select_folder_btn.Hide()
			self.play_button.Hide()
			self.sound_choice.Hide()
			self.select_sound_label.Hide()
		# Actualizamos la interfaz
		self.panel.Layout()

	def on_select_folder(self, event):
		"""
		Método que permite la selección de la carpeta para los sonidos.
		"""
		if self.custom_sound_check.IsChecked():
			# Iniciamos el diálogo de selección de carpeta.
			#Translators: Mensaje que solicita al usuario seleccionar la carpeta de sonidos desde el explorador.
			with wx.DirDialog(self, _("Seleccione la carpeta de sonidos"), style=wx.DD_DEFAULT_STYLE) as dialog:
				# Mostramos el diálogo y verificamos si el usuario presionó OK
				if dialog.ShowModal() == wx.ID_OK:
					# Obtenemos la carpeta seleccionada y la almacenamos en self.sound_folder
					self.sound_folder = dialog.GetPath()
					# llamamos a los métodos para cargar los archivos desde la carpeta y para guardar la selección en el archivo json.
					self.load_sounds_from_folder()
					self.save_sound_config()
		else:
			#Translators: Mensaje que indica al usuario que la casilla de sonido personalizado no está marcada.
			ui.message(_("La casilla para el sonido personalizado no está marcada."))


	def load_sounds_from_folder(self):
		"""
		Cargar los archivos de sonido de la carpeta seleccionada en el ComboBox.
		"""
		# Si sound_folder tiene contenido.
		if self.sound_folder:
			"""
			añadimos a la lista sounds los archivos que sean .wav.
			Primero definimos la lista 'sounds' utilizando un iterador 'f' para recorrer la carpeta 'sound_folder'.
			obtenemos sus archivos con os.listdir, luego con el mismo iterable, hacemos la verificación de si los archivos contienen la extención .wav, utilizando f.endswith(('.wav')).
			"""
			
			sounds = [f for f in os.listdir(self.sound_folder) if f.endswith(('.wav'))]
			# Añadimos los archivos obtenidos al ComboBox
			self.sound_choice.SetItems(sounds)
			#Si la lista sounds tiene contenido
			if sounds:
				# Seleccionamos el primer elemento en el ComboBox
				self.sound_choice.SetSelection(0)
				# Guardar el primer sonido seleccionado
				self.selected_sound = os.path.join(self.sound_folder, sounds[0])
				self.save_sound_config()

	def on_play_sound(self, event):
		"""
		Método que reproduce el sonido seleccionado por el usuario en el cuadro convinado
		"""
		if self.custom_sound_check.IsChecked():
			# Declaramos la variable sound y le asignamos el valor obtenido de self.sound_choice
			sound = self.sound_choice.GetValue()
			# Construímos la ruta completa al archivo.
			sound_path = os.path.join(self.sound_folder, sound)
			# Reproducimos con playWaveFile
			playWaveFile(sound_path)
		else:
			#Translators: Mensaje que indica al usuario que la casilla para el sonido personalizado no está marcada.
			ui.message(_("La casilla para el sonido personalizado no está marcada."))

	def add_reminder(self, event):
		"""
		Método para añadir el recordatorio.
		"""
		# obtenemos los datos ingresados por el usuario.
		custom_interval = None
		if self.custom_interval_field.GetValue():
			try:
				custom_interval = int(self.custom_interval_field.GetValue().strip())
				if custom_interval <= 0:
					raise ValueError
			except ValueError:
				#Translators: Mensaje de error que indica que el número para el intervalo debe de ser positivo, y número entero.
				wx.MessageBox(_("El intervalo personalizado debe ser un número entero positivo."), _("Error"), wx.ICON_ERROR)
				self.custom_interval_field.SetFocus()
				return
			
		message = self.message_field.GetValue()
		hours = self.hours_field.GetValue().strip()
		minutes = self.minutes_field.GetValue().strip()
		if not message or not hours or not minutes:
			# Mandamos un mensaje de error.
			#Translators: Mensaje de error notificando que los campos no pueden quedar sin contenido.
			wx.MessageBox(_("parece que alguno de los campos está sin contenido. Mensaje, horas y minutos son obligatorios. Por favor, verifica y vuelve a intentar."), _("Error"), wx.ICON_ERROR)
			# enfocamos el cuadro de mensaje y retornamos.
			self.message_field.SetFocus()
			return

		# Validamos que las horas y minutos sean números válidos
		try:
			hours = int(hours)
			minutes = int(minutes)
		except ValueError:
			#Translators: Mensaje de error que indica que las horas y minutos deben de ser números enteros válidos.
			wx.MessageBox(_("Las horas y minutos deben de ser números enteros válidos."), _("Error"), wx.ICON_ERROR)
			# Enfocamos el cuadro de horas y retornamos.
			self.hours_field.SetFocus()
			return
		# Validar si horas y minutos están dentro del rango.
		if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
			#Translators: Mensaje de error indicando al usuario que las horas y minutos ingresados están fuera del rango.
			wx.MessageBox(_("Rango no válido. Las horas deben de estar entre 00 y 23, y los minutos entre 00 y 59."), _("Error"), wx.ICON_ERROR)
			self.hours_field.SetFocus()
			return

		now = datetime.now()
	
		if self.specific_date_check.IsChecked():
			# Obtener la fecha del DatePickerCtrl y convertirla a datetime
			selected_date = self.date_picker.GetValue()
			py_date = selected_date.GetYear(), selected_date.GetMonth() + 1, selected_date.GetDay()
			reminder_time = datetime(py_date[0], py_date[1], py_date[2], hour=hours, minute=minutes, second=0, microsecond=0)
		
			# Validar que la fecha no sea en el pasado
			if reminder_time < now:
				#Translators: Mensaje de error indicando que la fecha seleccionada está en el pasado
				wx.MessageBox(_("La fecha y hora seleccionadas están en el pasado. Por favor, selecciona una fecha y hora futura."), _("Error"), wx.ICON_ERROR)
				return
		else:
			reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
			if reminder_time < now:
				reminder_time += timedelta(days=1)
		
		recurrence = self.recurrence_choice.GetValue() if self.recurrence_check.IsChecked() else None
		# Si se selecciona un sonido personalizado, se guarda el archivo seleccionado
		if self.custom_sound_check.IsChecked() and self.sound_choice.GetValue():
			self.selected_sound = os.path.join(self.sound_folder, self.sound_choice.GetValue())
		else:
			self.selected_sound = None
		self.reminder_manager.add_reminder(message, reminder_time, recurrence, self.selected_sound, custom_interval)

		self.message_field.Clear()
		self.hours_field.SetSelection(-1)
		self.minutes_field.SetSelection(-1)
		self.recurrence_check.SetValue(False)
		self.specific_date_check.SetValue(False)
		self.toggle_specific_date(None)
		self.recurrence_choice.Hide()
	#agregar atajos de teclado
	def setup_accelerators(self):
		#creamos identificadores para los atajos
		load_folder = wx.NewIdRef()
		play_file = wx.NewIdRef()
		close_window = wx.NewIdRef()
		close_window_esc = wx.NewIdRef()
		# Enlasar a eventos
		self.Bind(wx.EVT_MENU, self.on_select_folder, id=load_folder)
		self.Bind(wx.EVT_MENU, self.on_play_sound, id=play_file)
		self.Bind(wx.EVT_MENU, self.close, id=close_window)
		self.Bind(wx.EVT_MENU, self.close, id=close_window_esc)
		# Creamos los atajos
		accel_tbl = wx.AcceleratorTable([
			(wx.ACCEL_CTRL, ord("F"), load_folder),
			(wx.ACCEL_CTRL, ord("P"), play_file),
			(wx.ACCEL_CTRL, ord("Q"), close_window),
			(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, close_window_esc)
		])
		self.SetAcceleratorTable(accel_tbl)

	def donate(self, event):
		"""
		Método para abrir el navegador al enlace de paypal
		"""
		
		wx.LaunchDefaultBrowser("https://paypal.me/paymentToMl")

	def close(self, event):
		self.Destroy()


def disableInSecureMode(decoratedCls):
	if globalVars.appArgs.secure:
		return globalPluginHandler.GlobalPlugin
	return decoratedCls

@disableInSecureMode
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()

		config.conf.spec['remindersConfig'] = {
			"numberOfTimesToNotifyReminder": "integer(default=1)",
			"notificationInterval": "integer(default=10)"
		}
		settingsDialogs.NVDASettingsDialog.categoryClasses.append(remindersConfigPanel)
		self.add_to_tools_menu()

	def terminate(self, *args, **kwargs):
		super().terminate(*args, **kwargs)
		settingsDialogs.NVDASettingsDialog.categoryClasses.remove(remindersConfigPanel)

	def add_to_tools_menu(self):
		"""
		Añade un submenú 'Recordatorios' con las siguientes opciones:
		Añadir Recordatorio, Ver Recordatorios Activos y eliminar recordatorios
		al menú de herramientas.
		"""
		
		# Obtener el menú de herramientas.
		toolsMenu = gui.mainFrame.sysTrayIcon.toolsMenu

		# Crear el submenú de Recordatorios.
		remindersSubMenu = wx.Menu()

		# Crear los ítems del submenú.
		#Translators: Etiqueta para el item de menú añadir recordatorio.
		addReminderMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Añadir Recordatorio"))
		#Translators: Etiqueta para el item de menú ver recordatorios activos.
		viewRemindersMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Ver Recordatorios Activos"))
		#Translators: Etiqueta para el item de menú eliminar recordatorio.
		deleteReminderMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Eliminar Recordatorio"))

		# Añadir los ítems al submenú.
		remindersSubMenu.Append(addReminderMenuItem)
		remindersSubMenu.Append(viewRemindersMenuItem)
		remindersSubMenu.Append(deleteReminderMenuItem)

		# Añadir el submenú de Recordatorios al menú de herramientas.
		#Translators: Nombre para el submenú.
		toolsMenu.AppendSubMenu(remindersSubMenu, _("&Recordatorios"))

		# Vincular los eventos de clic a los nuevos ítems.
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.open_reminder_window, addReminderMenuItem)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.check_active_reminders, viewRemindersMenuItem)
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU, self.delete_reminder, deleteReminderMenuItem)

	def open_reminder_window(self, event):
		"""
		Abre la ventana principal de recordatorios para añadir uno nuevo.
		"""
		if not hasattr(self, 'frame') or not self.frame:
			self.frame = ReminderApp(None)
		elif not self.frame.IsShown():
			self.frame = ReminderApp(None)
		self.frame.Show()
	def check_active_reminders(self, event):
		"""
		Muestra los recordatorios activos en una ventana.
		"""
		if reminder_manager.reminders:
			reminder_list = []
			now = datetime.now()
		
			for index, (message, reminder_time, recurrence, sound_file, custom_interval) in enumerate(reminder_manager.reminders, start=1):
				formatted_time = reminder_time.strftime("%H:%M")
			
				# Verificar si el recordatorio es para hoy o para una fecha futura
				if reminder_time.date() == now.date():
					time_text = f"programado para hoy a las {formatted_time}"
				else:
					formatted_date = reminder_time.strftime("%d/%m/%Y")
					time_text = f"programado para el {formatted_date} a las {formatted_time}"
				
				recurrence_text = f", recurrente {recurrence}" if recurrence else ""
				reminder_list.append(f"{index}: {message}, {time_text}{recurrence_text}")
			
			reminders_text = "\n".join(reminder_list)
			#Translators: título de la ventana para los recordatorios activos.
			ui.browseableMessage(f"\n{reminders_text}", _("Recordatorios activos:"))
		else:
			#Translators: Mensaje que le indica al usuario que no hay recordatorios activos.
			ui.message(_("No hay recordatorios activos."))

	def delete_reminder(self, event):
		"""
		Permite eliminar un recordatorio activo a través de un diálogo de selección.
		"""
		if reminder_manager.reminders:
			now = datetime.now()
			# Crear una lista de los nombres (mensajes) de los recordatorios activos junto con índices visibles.
			reminder_messages = []
			
			for i, (message, reminder_time, _, _, _) in enumerate(reminder_manager.reminders):
				if reminder_time.date() == now.date():
					time_info = f"hoy a las {reminder_time.strftime('%H:%M')}"
				else:
					time_info = f"el {reminder_time.strftime('%d/%m/%Y')} a las {reminder_time.strftime('%H:%M')}"
				
				reminder_messages.append(f"{i + 1}: {message} ({time_info})")

			# Crear un diálogo de selección única con los recordatorios activos.
			#Translators: Mensaje y título del diálogo para eliminar recordatorios.
			dlg = wx.SingleChoiceDialog(
				None, 
				DELETE_REMINDER_MESSAGE, 
				DELETE_REMINDER_TITLE, 
				reminder_messages
			)

			if dlg.ShowModal() == wx.ID_OK:
				try:
					# Obtener el índice seleccionado basado en la lista generada.
					selection = dlg.GetSelection()
					if 0 <= selection < len(reminder_manager.reminders):
						# Eliminar el recordatorio seleccionado.
						removed_reminder = reminder_manager.reminders.pop(selection)
						# Guardar los cambios actualizados.
						reminder_manager.save_reminders()

						# Notificar al usuario que el recordatorio fue eliminado.
						#Mensaje y título de ventana que indican al usuario que el recordatorio ha sido eliminado.
						gui.messageBox(
							REMINDER_DELETED_MESSAGE.format(removed_reminder[0]),
							REMINDER_DELETED_TITLE
						)
					else:
						#Translators: Mensaje y título de ventana que le indican al usuario que el recordatorio seleccionado ya no existe.
						gui.messageBox(
							_("El recordatorio seleccionado ya no existe."), 
							_("Error"), 
							wx.ICON_ERROR
						)
				except Exception as e:
					#Translators: mensaje y título de ventana que le indican al usuario que ha ocurrido un error al intentar eliminar el recordatorio.
					gui.messageBox(
						_("Ocurrió un error al intentar eliminar el recordatorio:\n\n{}").format(str(e)), 
						_("Error"), 
						wx.ICON_ERROR
					)
			dlg.Destroy()
		else:
			#Translators: Mensaje que le indica al usuario que no hay recordatorios para poder eliminar.
			ui.message(_("No hay recordatorios para eliminar."))

	@scriptHandler.script(
		#Translators: Descripción para el gesto que lanza la ventana de recordatorios.
		description=_("Abrir la ventana de recordatorios"),
		#Translators: Nombre de la categoría.
		category=_("Recordatorios"),
		gesture=None
	)
	def script_open_reminder_window(self, gesture):
		self.open_reminder_window(None)

	@scriptHandler.script(
		#Translators: Descripción del gesto para ver recordatorios activos.
		description=_("Verificar recordatorios activos"),
		#Translators: Nombre de la categoría.
		category=_("Recordatorios"),
		gesture=None
	)
	
	def script_check_active_reminders(self, gesture):
		self.check_active_reminders(None)

	@scriptHandler.script(
		#Translators: Descripción del gesto que lanza la ventana para eliminar recordatorios.
		description=_("Lanza el diálogo para eliminar recordatorios"),
		#Translators: Nombre de la categoría.
		category=_("Recordatorios"),
		gesture=None
	)
	def script_open_delete_dialog(self, gesture):
		wx.CallAfter(self.delete_reminder, None)

reminder_manager = ReminderManager()


class remindersConfigPanel(settingsDialogs.SettingsPanel):
	#Translators: Título de la ventana para la configuración del complemento.
	title=_("Configuración de recordatorios")
	def makeSettings(self, sizer):
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)
		#Translators: Etiqueta que le indica al usuario que debe seleccionar un número para las notificaciones que llegarán.
		self.numberOfTimesToNotifyReminder_label = helper.addItem(wx.StaticText(self, label=_("Selecciona el número de notificaciones que llegarán para el recordatorio.")))
		self.numberOfTimesToNotifyReminder = helper.addItem(wx.ComboBox(self, choices=["1", "2", "3", "4"], style=wx.CB_READONLY))
		self.numberOfTimesToNotifyReminder.SetStringSelection(str(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"]))
		#Translators: Etiqueta que solicita al usuario seleccionar (en segundos) el tiempo entre las notificaciones.
		self.notificationInterval_label = helper.addItem(wx.StaticText(self, label=_("Selecciona el intervalo de tiempo para las notificaciones (en segundos).")))
		self.notificationInterval = helper.addItem(wx.ComboBox(self, choices=["5", "10", "20", "40", "60"], style=wx.CB_READONLY))
		self.notificationInterval.SetStringSelection(str(config.conf["remindersConfig"]["notificationInterval"]))

	def onSave(self):
		config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"] = int(self.numberOfTimesToNotifyReminder.GetStringSelection())
		config.conf["remindersConfig"]["notificationInterval"] = int(self.notificationInterval.GetStringSelection())

