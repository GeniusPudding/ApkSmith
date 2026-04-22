"""Tests for adb helpers and doctor."""

from unittest.mock import patch

import pytest

from apksmith.toolchain.adb import (
    find_adb,
    get_package_apk_paths,
    require_device,
)
from apksmith.toolchain.tools import ToolNotFoundError


class TestFindAdb:
    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: None)
        with pytest.raises(ToolNotFoundError, match="adb"):
            find_adb()

    def test_returns_override(self):
        assert find_adb("/custom/adb") == "/custom/adb"


class TestRequireDevice:
    def test_no_devices_raises(self):
        with patch("apksmith.toolchain.adb.list_devices", return_value=[]), \
             pytest.raises(RuntimeError, match="No Android devices"):
            require_device()

    def test_single_device_auto_selects(self):
        devs = [{"serial": "emulator-5554", "state": "device"}]
        with patch("apksmith.toolchain.adb.list_devices", return_value=devs):
            assert require_device() == "emulator-5554"

    def test_multiple_devices_without_serial_raises(self):
        devs = [
            {"serial": "emulator-5554", "state": "device"},
            {"serial": "ABCD1234", "state": "device"},
        ]
        with patch("apksmith.toolchain.adb.list_devices", return_value=devs), \
             pytest.raises(RuntimeError, match="Multiple devices"):
            require_device()

    def test_multiple_devices_with_serial_ok(self):
        devs = [
            {"serial": "emulator-5554", "state": "device"},
            {"serial": "ABCD1234", "state": "device"},
        ]
        with patch("apksmith.toolchain.adb.list_devices", return_value=devs):
            assert require_device("ABCD1234") == "ABCD1234"

    def test_serial_not_found_raises(self):
        devs = [{"serial": "emulator-5554", "state": "device"}]
        with patch("apksmith.toolchain.adb.list_devices", return_value=devs), \
             pytest.raises(RuntimeError, match="not found"):
            require_device("NONEXISTENT")


class TestGetPackagePaths:
    def test_parses_pm_path_output(self):
        fake_output = "package:/data/app/~~abc/com.example-def/base.apk\n"
        with patch("apksmith.toolchain.adb._adb", return_value=fake_output):
            paths = get_package_apk_paths("com.example", serial="emu")
            assert paths == ["/data/app/~~abc/com.example-def/base.apk"]

    def test_split_apk(self):
        fake_output = (
            "package:/data/app/~~x/com.ex-y/base.apk\n"
            "package:/data/app/~~x/com.ex-y/split_config.arm64_v8a.apk\n"
            "package:/data/app/~~x/com.ex-y/split_config.en.apk\n"
        )
        with patch("apksmith.toolchain.adb._adb", return_value=fake_output):
            paths = get_package_apk_paths("com.ex", serial="emu")
            assert len(paths) == 3

    def test_not_found_raises(self):
        with patch("apksmith.toolchain.adb._adb", return_value=""), \
             pytest.raises(RuntimeError, match="not found on device"):
            get_package_apk_paths("com.fake", serial="emu")


class TestCliHelp:
    """Verify every subcommand has working --help."""

    @pytest.mark.parametrize("cmd", ["doctor", "pull", "instrument", "install"])
    def test_help_exits_zero(self, cmd):
        from apksmith.cli import main
        with pytest.raises(SystemExit) as exc_info:
            main([cmd, "--help"])
        assert exc_info.value.code == 0

    def test_top_level_help(self):
        from apksmith.cli import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
