"""Regression coverage for passive and explicit ADB discovery."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from autoclicker.gui.device_discovery import discover_devices


class DeviceDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.clicker = Mock()
        self.clicker._ensure_adb_server.return_value = True
        self.clicker._run_adb_stage.return_value = SimpleNamespace(
            stdout="List of devices attached\n"
        )
        self.clicker.normalize_device_serials.side_effect = (
            lambda devices: list(dict.fromkeys(devices))
        )

    def test_default_refresh_never_connects_to_other_ports(self):
        self.clicker._run_adb_stage.return_value = SimpleNamespace(
            stdout=(
                "List of devices attached\n"
                "emulator-5554\tdevice product:test\n"
                "127.0.0.1:5575\toffline\n"
                "127.0.0.1:5555\tunauthorized\n"
            )
        )
        self.assertEqual(discover_devices(self.clicker), ["emulator-5554"])
        self.clicker._run_adb_stage.assert_called_once_with(
            "디바이스 목록 조회", ["devices"]
        )
        self.clicker.get_connected_devices.assert_not_called()

    def test_empty_device_list(self):
        self.assertEqual(discover_devices(self.clicker), [])
        self.clicker.get_connected_devices.assert_not_called()

    def test_no_adb_server_returns_empty_without_probing(self):
        self.clicker._ensure_adb_server.return_value = False
        self.assertEqual(discover_devices(self.clicker), [])
        self.clicker._run_adb_stage.assert_not_called()
        self.clicker.get_connected_devices.assert_not_called()

    def test_adb_devices_failure_is_safe(self):
        self.clicker._run_adb_stage.return_value = None
        self.assertEqual(discover_devices(self.clicker), [])
        self.clicker.get_connected_devices.assert_not_called()

    def test_port_scan_requires_explicit_request(self):
        self.clicker.get_connected_devices.return_value = ["127.0.0.1:5555"]
        self.assertEqual(
            discover_devices(self.clicker, scan_ports=True), ["127.0.0.1:5555"]
        )
        self.clicker.get_connected_devices.assert_called_once_with()
        self.clicker._ensure_adb_server.assert_not_called()
        self.clicker._run_adb_stage.assert_not_called()

    def test_duplicate_online_serials_are_normalized(self):
        self.clicker._run_adb_stage.return_value = SimpleNamespace(
            stdout="emulator-5554\tdevice\nemulator-5554\tdevice\n"
        )
        self.assertEqual(discover_devices(self.clicker), ["emulator-5554"])


if __name__ == "__main__":
    unittest.main()
