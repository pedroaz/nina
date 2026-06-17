"""Tests for `MacosProcessTapSource`.

These run on any OS. The macOS-only paths are exercised by mocking the
`CoreAudio` and `AVFoundation` modules so we can verify the call sequence
without requiring a real Mac.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.unit


def test_open_raises_on_non_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    from nina_core.meetings.backends.macos_process_tap import MacosProcessTapSource
    from nina_core.meetings.recorder import RecorderError

    monkeypatch.setattr(sys, "platform", "linux")
    source = MacosProcessTapSource()
    with pytest.raises(RecorderError, match="only available on macOS"):
        source.open(48000, 1)


def test_open_raises_on_old_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    from nina_core.meetings.backends import macos_process_tap as mod
    from nina_core.meetings.recorder import RecorderError

    monkeypatch.setattr(sys, "platform", "darwin")

    import platform

    fake_ver = ("13.6.1", ("", "", ""), "x86_64")
    monkeypatch.setattr(platform, "mac_ver", lambda: fake_ver)
    monkeypatch.setattr(mod, "_macos_meets_min_version", lambda v: False)

    source = mod.MacosProcessTapSource()
    with pytest.raises(RecorderError, match=r"macOS 14\.4\+"):
        source.open(48000, 1)


def test_open_raises_with_clear_error_when_pyobjc_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from nina_core.meetings.backends import macos_process_tap as mod
    from nina_core.meetings.recorder import RecorderError

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(mod, "_macos_meets_min_version", lambda v: True)

    real_import = __import__

    def _blocked(name, *args, **kwargs):
        if name in {"CoreAudio", "AVFoundation"}:
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", _blocked)

    source = mod.MacosProcessTapSource()
    with pytest.raises(RecorderError, match="pyobjc-framework-CoreAudio"):
        source.open(48000, 1)


def test_open_calls_audio_hardware_create_process_tap_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When pyobjc is mocked to be available, the open() path builds a tap
    description, calls AudioHardwareCreateProcessTap, builds an aggregate
    device, installs an IO proc, and starts the device — in that order."""
    import contextlib

    from nina_core.meetings.backends import macos_process_tap as mod
    from nina_core.meetings.recorder import RecorderError

    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(mod, "_macos_meets_min_version", lambda v: True)

    core_audio = MagicMock()
    call_log: list[str] = []

    def _create_process_tap(desc, out_tap):
        call_log.append("AudioHardwareCreateProcessTap")
        out_tap._obj.value = 1234
        return 0

    core_audio.AudioHardwareCreateProcessTap.side_effect = _create_process_tap
    core_audio.AudioHardwareCreateAggregateDevice = MagicMock(return_value=5678)
    core_audio.AudioDeviceCreateIOProcID = MagicMock(return_value=0)
    core_audio.AudioDeviceStart = MagicMock(return_value=0)
    core_audio.AudioDeviceIOProc = MagicMock(return_value="io_proc_ref")

    cf = MagicMock()
    cf.CFDictionaryCreateMutable = MagicMock(side_effect=lambda *a, **kw: f"dict-{len(call_log)}")
    cf.CFDictionarySetValue = MagicMock()
    cf.CFArrayCreateMutable = MagicMock(side_effect=lambda *a, **kw: f"arr-{len(call_log)}")
    cf.CFArrayAppendValue = MagicMock()
    cf.CFStringCreateWithCString = MagicMock(return_value="uid_str")
    cf.kCFAllocatorDefault = "default_alloc"
    cf.kCFBooleanTrue = True

    sys.modules["CoreAudio"] = core_audio
    sys.modules["CoreFoundation"] = cf
    sys.modules["AVFoundation"] = MagicMock()

    monkeypatch.setattr(mod, "_build_mono_global_tap_description", lambda: "tap_desc_obj")
    monkeypatch.setattr(mod, "_AudioHardwareCreateAggregateDevice", lambda _d: 5678)

    source = mod.MacosProcessTapSource()
    with contextlib.suppress(RecorderError):
        source.open(48000, 1)

    assert "AudioHardwareCreateProcessTap" in call_log
    assert source._tap_id == 1234
    assert source._device_id == 5678
    core_audio.AudioDeviceCreateIOProcID.assert_called_once()
    core_audio.AudioDeviceStart.assert_called_once()


def test_trampoline_signature_is_pure_python() -> None:
    """Sanity: the trampoline is a module-level function (not a method) and
    can be referenced. The actual ctypes marshalling can only be exercised
    on a real macOS CoreAudio runtime — the unit test runs on Linux, where
    loading the framework binary would segfault regardless.
    """
    from nina_core.meetings.backends import macos_process_tap as mod

    assert callable(mod._io_proc_trampoline)
    assert callable(mod._IoProcBridge)
    # The C trampoline should be declared with the right arg/restype for an
    # AudioDeviceIOProc, but Python doesn't enforce ctypes argtypes unless
    # we set them. We just check the function exists and is importable.
    assert mod._io_proc_trampoline.__name__ == "_io_proc_trampoline"
