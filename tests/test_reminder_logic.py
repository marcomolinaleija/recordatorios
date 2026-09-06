"""Pruebas de la lógica independiente de una instancia real de NVDA."""

import builtins
import importlib.util
import json
import logging
import sys
import tempfile
import threading
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "recordatorios_test"


def _install_stubs():
    builtins._ = lambda message: message
    addon_handler = types.ModuleType("addonHandler")
    addon_handler.initTranslation = lambda: None
    sys.modules["addonHandler"] = addon_handler

    wx = types.ModuleType("wx")
    wx.NewIdRef = lambda: object()
    wx.CallAfter = lambda callback, *args: callback(*args)
    wx.CallLater = lambda _delay, callback, *args: callback(*args)
    wx.ID_OK = 1
    sys.modules["wx"] = wx

    config = types.ModuleType("config")
    config.conf = {"remindersConfig": {"notificationInterval": 1, "numberOfTimesToNotifyReminder": 1}}
    sys.modules["config"] = config
    sys.modules["globalVars"] = types.ModuleType("globalVars")
    sys.modules["gui"] = types.ModuleType("gui")
    tones = types.ModuleType("tones")
    tones.beep = lambda *_args: None
    sys.modules["tones"] = tones
    ui = types.ModuleType("ui")
    ui.message = lambda _message: None
    sys.modules["ui"] = ui
    nvwave = types.ModuleType("nvwave")
    nvwave.playWaveFile = lambda _path: None
    sys.modules["nvwave"] = nvwave
    log_handler = types.ModuleType("logHandler")
    log_handler.log = logging.getLogger("recordatorios-tests")
    sys.modules["logHandler"] = log_handler


def _load_module(name, file_name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "addon" / "globalPlugins" / "recordatorios" / file_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_install_stubs()
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "addon" / "globalPlugins" / "recordatorios")]
sys.modules[PACKAGE] = package
recurrence = _load_module(f"{PACKAGE}.recurrence", "recurrence.py")
constants = _load_module(f"{PACKAGE}.constants", "constants.py")
manager_module = _load_module(f"{PACKAGE}.manager", "manager.py")


def _manager_at(path):
    manager = manager_module.ReminderManager.__new__(manager_module.ReminderManager)
    manager.reminders = []
    manager._lock = threading.Lock()
    manager._stop_event = threading.Event()
    manager.file_path = str(path)
    return manager


class RecurrenceTests(unittest.TestCase):
    def test_daily_occurrence_skips_all_missed_days(self):
        original = datetime(2026, 1, 1, 9, 0)
        after = datetime(2026, 1, 4, 10, 0)
        self.assertEqual(
            recurrence.next_occurrence(original, recurrence.RECURRENCE_DAILY, None, after),
            datetime(2026, 1, 5, 9, 0),
        )

    def test_custom_occurrence_skips_all_missed_intervals(self):
        original = datetime(2026, 1, 1, 9, 0)
        after = datetime(2026, 1, 1, 10, 1)
        self.assertEqual(
            recurrence.next_occurrence(original, recurrence.RECURRENCE_CUSTOM, 15, after),
            datetime(2026, 1, 1, 10, 15),
        )


class ManagerTests(unittest.TestCase):
    def test_updates_and_removes_by_id_not_by_current_position(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager_at(Path(directory) / "recordatorios.json")
            first = manager_module.new_reminder("primero", datetime.now() + timedelta(hours=1))
            second = manager_module.new_reminder("segundo", datetime.now() + timedelta(hours=2))
            second["pending_review"] = True
            manager.reminders = [first, second]
            self.assertTrue(manager.update_reminder(second["id"], message="actualizado"))
            self.assertEqual(manager.reminders[1]["message"], "actualizado")
            self.assertFalse(manager.reminders[1]["pending_review"])
            self.assertEqual(manager.remove(first["id"])["id"], first["id"])
            self.assertEqual(manager.reminders[0]["id"], second["id"])

    def test_save_is_valid_json_and_migration_adds_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recordatorios.json"
            manager = _manager_at(path)
            manager.reminders = [manager_module.new_reminder("prueba", datetime(2026, 1, 1, 10, 0))]
            with manager._lock:
                manager._save_unlocked()
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw[0]["message"], "prueba")
            self.assertTrue(raw[0]["id"])

            legacy = [{"message": "antiguo", "time": "2026-01-02 10:00", "recurrence": None, "sound_file": None, "custom_interval": None, "tasks": []}]
            path.write_text(json.dumps(legacy), encoding="utf-8")
            manager.load_reminders()
            self.assertEqual(len(manager.reminders), 1)
            self.assertTrue(manager.reminders[0]["id"])

    def test_invalid_file_is_backed_up_without_being_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recordatorios.json"
            path.write_text("{ no es JSON", encoding="utf-8")
            manager = _manager_at(path)
            manager.load_reminders()
            self.assertEqual(path.read_text(encoding="utf-8"), "{ no es JSON")
            self.assertEqual(len(list(Path(directory).glob("recordatorios.json.*.bak"))), 1)

    def test_due_incomplete_reminder_is_retained_pending_review(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = _manager_at(Path(directory) / "recordatorios.json")
            reminder = manager_module.new_reminder(
                "tarea", datetime.now() - timedelta(minutes=1), tasks=[{"description": "pendiente", "completed": False}],
            )
            manager.reminders = [reminder]
            manager._show_incomplete_task_dialog = lambda _reminder: None
            manager._check_due_reminders()
            self.assertEqual(len(manager.reminders), 1)
            self.assertTrue(manager.reminders[0]["pending_review"])


if __name__ == "__main__":
    unittest.main()
