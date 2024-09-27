# Recordatorios. complemento para NVDA.
# Este archivo está cubierto por la Licencia Pública General GNU
# Consulte el archivo COPYING.txt para obtener más detalles.
# Copyright (C) 2024 Marco Leija <marcomolinaleija@hotmail.com>


import wx
import threading
import time
import json
import os
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

	def add_reminder(self, message, reminder_time, recurrence=None, sound_file=None):
		"""
		Método que añade un recordatorio, verificando si no existe otro con el mismo nombre
		Args:
			message (str): El mensaje del recordatorio.
			reminder_time (datetime): La hora en la que llegará el recordatorio.
			recurrence (str): La frecuencia del recordatorio. diario, semanal, mensual, si aplica.
			sound_file (str): ruta con el sonido para el recordatorio
		"""
		# iteramos sobre la lista de recordatorios utilizando existing_message como iterador
		for existing_message, _, _ , _, in self.reminders:
			# si existing_message convertido todos sus caracteres a minúsculas es igual a message, también convertidos sus caracteres a minúsculas:
			if existing_message.lower() == message.lower():
				# Notifica al usuario mediante ui.message
				ui.message(f"Ya existe un recordatorio con el nombre '{message}'.")
				return
		# en caso contrario, se añade el recordatorio y se notifica mediante ui.message
		self.reminders.append((message, reminder_time, recurrence, sound_file))
		ui.message(f"Recordatorio agregado para {reminder_time.strftime('%H:%M')}")
		# llamamos al método para guardar los recordatorios
		self.save_reminders()

	def check_reminders(self):
		"""
		Método que verifica periódicamente si hay recordatorios que deben ser notificados.
		"""
		# Mientras que self.running sea True
		while self.running:
			# obtenemos la hora actual
			now = datetime.now()
			# Recorremos la lista de recordatorios
			for reminder in self.reminders[:]:
				message, reminder_time, recurrence, sound_file = reminder
				# Si el tiempo del recordatorio ya ha pasado se notificará al usuario
				if reminder_time <= now:
					# llamada al método notify para notificar al usuario
					self.notify(message, sound_file)
					# si el recordatorio es recurrente:
					if recurrence:
						# si el recordatorio es diario, se reprogramará para el día siguiente
						if recurrence == "diario":
							reminder_time += timedelta(days=1)
						# Si el recordatorio es semanal, hace lo mismo. se reprograma para la misma hora y la siguiente semana
						elif recurrence == "semanal":
							reminder_time += timedelta(weeks=1)
						# Si es mensual, se reprograma para el siguiente mes en la misma fecha
						elif recurrence == "mensual":
							reminder_time = self.add_month(reminder_time)
						# Eliminamos el recordatorio anterior para añadir el reprogramado.
						self.reminders.remove(reminder)
						self.reminders.append((message, reminder_time, recurrence, sound_file))
					else:
						# Y si no es recurrente, entonces solo eliminamos el recordatorio.
						self.reminders.remove(reminder)
					# Actualizamos los recordatorios
					self.save_reminders()
			# Verificamos cada segundo
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
		self.interval = int(config.conf["remindersConfig"]["notificationInterval"])
		num_times = int(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"])

		for i in range(num_times):
			if sound_file and os.path.exists(sound_file):
				# Reproducir el sonido personalizado usando nvwave
				ui.message(f"Recordatorio: {message}")
				playWaveFile(sound_file)
			else:
				# Reproducir sonido para la notificación
				tones.beep(440, 500)
				ui.message(f"Recordatorio: {message}")
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
			reminders_data = [(msg, time.strftime('%Y-%m-%d %H:%M'), rec, sound_file) for msg, time, rec, sound_file in self.reminders]
			# Escribimos la lista de los recordatorios en el archivo con formato json
			json.dump(reminders_data, file)

	def load_reminders(self):
		"""
		Método para cargar los recordatorios desde el archivo json
		"""
		# Verificamos si existe antes de cargarlo
		if os.path.exists(self.file_path):
			# Si existe, lo abrimos en modo lectura ('r')
			with open(self.file_path, 'r') as file:
				# Cargamos los datos del archivo en la variable reminders_data como json
				reminders_data = json.load(file)
				# Convertimos los datos cargados a la estructura de recordatorios,  convirtiendo el tiempo de cadena a un objeto datetime.
				self.reminders = [(msg, datetime.strptime(time, '%Y-%m-%d %H:%M'), rec, sound_file) for msg, time, rec, sound_file in reminders_data]



class ReminderApp(wx.Frame):
	"""
	Clase que contiene la interfaz para añadir un nuevo recordatorio.
	Hereda de wx.frame.
	"""
	
	def __init__(self, *args, **kw):
		super(ReminderApp, self).__init__(*args, **kw)
		
		# Configuramos el título de la ventana y el tamaño de la misma
		self.SetTitle("Añadir recordatorio")
		self.SetSize((400, 400))
		# Variables para el sonido personalizado
		self.sound_folder = None
		self.selected_sound = None
		

		# Creamos el panel que contendrá los elementos de la interfaz
		self.panel = wx.Panel(self)
		self.create_interface()
		self.setup_accelerators()

		self.reminder_manager = reminder_manager
		self.Bind(wx.EVT_CLOSE, self.close)


		# Cargar la configuración de sonidos
		self.load_sound_config()

	def save_sound_config(self):
		"""Guarda la carpeta de sonidos y el archivo seleccionado en el JSON."""
		config_path = os.path.join(globalVars.appArgs.configPath, "sonidos_recordatorios.json")
		with open(config_path, 'w') as file:
			config_data = {
				"sound_folder": self.sound_folder,
				"selected_sound": self.selected_sound
			}
			json.dump(config_data, file)

	def load_sound_config(self):
		"""Carga la configuración de sonidos (carpeta y archivo) desde el JSON."""
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
		sizer = wx.BoxSizer(wx.VERTICAL)

		message_label = wx.StaticText(self.panel, label="&Mensaje del Recordatorio:")
		sizer.Add(message_label, 0, wx.ALL | wx.EXPAND, 5)

		self.message_field = wx.TextCtrl(self.panel)
		sizer.Add(self.message_field, 0, wx.ALL | wx.EXPAND, 5)

		hours_label = wx.StaticText(self.panel, label="&Hora (formato 24h):")
		sizer.Add(hours_label, 0, wx.ALL | wx.EXPAND, 5)

		self.hours_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(24)], style=wx.CB_DROPDOWN)
		sizer.Add(self.hours_field, 0, wx.ALL | wx.EXPAND, 5)

		minutes_label = wx.StaticText(self.panel, label="&Minutos:")
		sizer.Add(minutes_label, 0, wx.ALL | wx.EXPAND, 5)

		self.minutes_field = wx.ComboBox(self.panel, choices=[str(i).zfill(2) for i in range(60)], style=wx.CB_DROPDOWN)
		sizer.Add(self.minutes_field, 0, wx.ALL | wx.EXPAND, 5)

		self.recurrence_check = wx.CheckBox(self.panel, label="&Recordatorio recurrente")
		sizer.Add(self.recurrence_check, 0, wx.ALL | wx.EXPAND, 5)
		self.recurrence_check.Bind(wx.EVT_CHECKBOX, self.toggle_recurrence)

		# Etiqueta y ComboBox para seleccionar la recurrencia
		recurrence_label = wx.StaticText(self.panel, label="Selecciona la frecuencia con la que llegará el recordatorio.")
		sizer.Add(recurrence_label, 0, wx.ALL | wx.EXPAND, 5)
		recurrence_label.Hide()
		self.recurrence_choice = wx.ComboBox(self.panel, choices=["diario", "semanal", "mensual"], style=wx.CB_READONLY)
		sizer.Add(self.recurrence_choice, 0, wx.ALL | wx.EXPAND, 5)
		self.recurrence_choice.SetSelection(0)
		self.recurrence_choice.Hide()
		# Checkbox para habilitar sonido personalizado
		self.custom_sound_check = wx.CheckBox(self.panel, label="&Usar sonido personalizado")
		sizer.Add(self.custom_sound_check, 0, wx.ALL | wx.EXPAND, 5)
		self.custom_sound_check.Bind(wx.EVT_CHECKBOX, self.toggle_custom_sound)
		# ComboBox para mostrar los sonidos en la carpeta seleccionada
		select_sound_label = wx.StaticText(self.panel, label="Selecciona un sonido de la lista.")
		sizer.Add(select_sound_label, 0, wx.ALL | wx.EXPAND, 5)
		select_sound_label.Hide()
		self.sound_choice = wx.ComboBox(self.panel, choices=[], style= wx.CB_READONLY)
		sizer.Add(self.sound_choice, 0, wx.ALL | wx.EXPAND, 5)
		self.sound_choice.Hide()

		self.play_button = wx.Button(self.panel, label="Reproducir  ctrl+p")
		sizer.Add(self.play_button, 0, wx.ALL | wx.CENTER, 5)
		self.play_button.Bind(wx.EVT_BUTTON, self.on_play_sound)
		self.play_button.Hide()

		# Botón para seleccionar carpeta de sonidos
		self.select_folder_btn = wx.Button(self.panel, label="Seleccionar carpeta de sonidos  ctrl+f")
		sizer.Add(self.select_folder_btn, 0, wx.ALL | wx.CENTER, 5)
		self.select_folder_btn.Bind(wx.EVT_BUTTON, self.on_select_folder)
		self.select_folder_btn.Hide()

		add_button = wx.Button(self.panel, label="&Agregar Recordatorio")
		sizer.Add(add_button, 0, wx.ALL | wx.CENTER, 5)
		add_button.Bind(wx.EVT_BUTTON, self.add_reminder)

		cancel_button = wx.Button(self.panel, label="Salir  ctrl+q")
		sizer.Add(cancel_button, 0, wx.ALL | wx.CENTER, 5)
		cancel_button.Bind(wx.EVT_BUTTON, self.close)

		self.panel.SetSizer(sizer)

	def toggle_recurrence(self, event):
		if self.recurrence_check.IsChecked():
			self.recurrence_choice.Show()
			recurrence_label.Show()
		else:
			self.recurrence_choice.Hide()
			recurrence_label.Hide()
		self.panel.Layout()

	def toggle_custom_sound(self, event):
		if self.custom_sound_check.IsChecked():
			self.select_folder_btn.Show()
			self.play_button.Show()
			self.sound_choice.Show()
			select_sound_label.Show()
		else:
			self.select_folder_btn.Hide()
			self.play_button.Hide()
			self.sound_choice.Hide()
			select_sound_label.Hide()
		self.panel.Layout()

	def on_select_folder(self, event):
		"""
		Permitir al usuario seleccionar una carpeta desde donde cargar los archivos de sonido.
		"""
		with wx.DirDialog(self, "Seleccione la carpeta de sonidos", style=wx.DD_DEFAULT_STYLE) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				self.sound_folder = dialog.GetPath()
				self.load_sounds_from_folder()
				self.save_sound_config()


	def load_sounds_from_folder(self):
		"""
		Cargar los archivos de sonido de la carpeta seleccionada en el ComboBox.
		"""
		if self.sound_folder:
			sounds = [f for f in os.listdir(self.sound_folder) if f.endswith(('.wav'))]
			self.sound_choice.SetItems(sounds)
			if sounds:
				self.sound_choice.SetSelection(0)
				# Guardar el primer sonido seleccionado
				self.selected_sound = os.path.join(self.sound_folder, sounds[0])
				self.save_sound_config()

	def on_play_sound(self, event):
		"""
		Método que reproduce el sonido seleccionado por el usuario en el cuadro convinado
		"""
		sound = self.sound_choice.GetValue()
		sound_path = os.path.join(self.sound_folder, sound)
		playWaveFile(sound_path)

	def add_reminder(self, event):
		message = self.message_field.GetValue()
		hours = int(self.hours_field.GetValue())
		minutes = int(self.minutes_field.GetValue())

		now = datetime.now()
		reminder_time = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

		if reminder_time < now:
			reminder_time += timedelta(days=1)
		recurrence = self.recurrence_choice.GetValue() if self.recurrence_check.IsChecked() else None
		# Si se selecciona un sonido personalizado, se guarda el archivo seleccionado
		if self.custom_sound_check.IsChecked() and self.sound_choice.GetValue():
			self.selected_sound = os.path.join(self.sound_folder, self.sound_choice.GetValue())
		else:
			self.selected_sound = None

		self.reminder_manager.add_reminder(message, reminder_time, recurrence, self.selected_sound)

		self.message_field.Clear()
		self.hours_field.SetSelection(-1)
		self.minutes_field.SetSelection(-1)
		self.recurrence_check.SetValue(False)
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

	def close(self, event):
		self.Destroy()

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
		addReminderMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Añadir Recordatorio"))
		viewRemindersMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Ver Recordatorios Activos"))
		deleteReminderMenuItem = wx.MenuItem(remindersSubMenu, wx.ID_ANY, _("Eliminar Recordatorio"))

		# Añadir los ítems al submenú.
		remindersSubMenu.Append(addReminderMenuItem)
		remindersSubMenu.Append(viewRemindersMenuItem)
		remindersSubMenu.Append(deleteReminderMenuItem)

		# Añadir el submenú de Recordatorios al menú de herramientas.
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
			for index, (message, reminder_time, recurrence, sound_file) in enumerate(reminder_manager.reminders, start=1):
				formatted_time = reminder_time.strftime("%H:%M")
				recurrence_text = f", recurrente {recurrence}" if recurrence else ""
				reminder_list.append(f"{index}: {message}, programado para las {formatted_time}{recurrence_text}")
			reminders_text = "\n".join(reminder_list)
			ui.browseableMessage(f"\n{reminders_text}", "Recordatorios activos:")
		else:
			ui.message("No hay recordatorios activos.")

	def delete_reminder(self, event):
		"""
		Permite eliminar un recordatorio activo a través de un diálogo de selección.
		"""
		if reminder_manager.reminders:
			# Crear una lista de los nombres (mensajes) de los recordatorios activos.
			reminder_messages = [message for message, _, _, _ in reminder_manager.reminders]
			
			# Crear un diálogo de selección única con los recordatorios activos.
			dlg = wx.SingleChoiceDialog(None, "Selecciona el recordatorio que deseas eliminar:", "Eliminar Recordatorio", reminder_messages)
			
			if dlg.ShowModal() == wx.ID_OK:
				# Obtener el índice del recordatorio seleccionado.
				selection = dlg.GetSelection()
				# Eliminar el recordatorio seleccionado.
				removed_reminder = reminder_manager.reminders.pop(selection)
				# Guardar los cambios actualizados.
				reminder_manager.save_reminders()
				
				# Notificar al usuario que el recordatorio fue eliminado.
				gui.messageBox(f"Recordatorio '{removed_reminder[0]}' eliminado.", "Información")
			dlg.Destroy()
		else:
			ui.message("No hay recordatorios para eliminar.")



	@scriptHandler.script(
		description="Abrir la ventana de recordatorios",
		category="Recordatorios",
		gesture=None
	)
	def script_open_reminder_window(self, gesture):
		if not hasattr(self, 'frame') or not self.frame:
			self.frame = ReminderApp(None)
		elif not self.frame.IsShown():
			self.frame = ReminderApp(None)
		self.frame.Show()

	@scriptHandler.script(
		description="Verificar recordatorios activos",
		category="Recordatorios",
		gesture=None
	)
	
	def script_check_active_reminders(self, gesture):
		if reminder_manager.reminders:
			reminder_list = []
			for index, (message, reminder_time, recurrence, sound_file) in enumerate(reminder_manager.reminders, start=1):
				formatted_time = reminder_time.strftime("%H:%M")
				recurrence_text = f", recurrente {recurrence}" if recurrence else ""
				reminder_list.append(f"{index}: {message}, programado para las {formatted_time}{recurrence_text}")
			reminders_text = "\n".join(reminder_list)
			ui.browseableMessage(f"\n{reminders_text}", "Recordatorios activos:")
		else:
			ui.message("No hay recordatorios activos.")

# Instanciar el gestor de recordatorios
reminder_manager = ReminderManager()

class remindersConfigPanel(settingsDialogs.SettingsPanel):
	title="Configuración de recordatorios"
	def makeSettings(self, sizer):
		helper = gui.guiHelper.BoxSizerHelper(self, sizer=sizer)
		self.numberOfTimesToNotifyReminder_label = helper.addItem(wx.StaticText(self, label="Selecciona el número de notificaciones que llegarán para el recordatorio."))
		self.numberOfTimesToNotifyReminder = helper.addItem(wx.ComboBox(self, choices=["1", "2", "3", "4"], style=wx.CB_READONLY))
		self.numberOfTimesToNotifyReminder.SetStringSelection(str(config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"]))
		self.notificationInterval_label = helper.addItem(wx.StaticText(self, label="Selecciona el intervalo de tiempo para las notificaciones (en segundos)."))
		self.notificationInterval = helper.addItem(wx.ComboBox(self, choices=["5", "10", "20"], style=wx.CB_READONLY))
		self.notificationInterval.SetStringSelection(str(config.conf["remindersConfig"]["notificationInterval"]))

	def onSave(self):
		config.conf["remindersConfig"]["numberOfTimesToNotifyReminder"] = int(self.numberOfTimesToNotifyReminder.GetStringSelection())
		config.conf["remindersConfig"]["notificationInterval"] = int(self.notificationInterval.GetStringSelection())
