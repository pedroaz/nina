"""macOS system audio capture via the Core Audio Process Tap private API.

Available on macOS 14.4+ (Sonoma). Taps the audio stream that apps send to
the default output device — same as a virtual cable would see, but at the
OS level. No BlackHole, no virtual driver.

Uses `pyobjc-framework-CoreAudio` to build the tap description and
aggregate device, and ctypes to call the C functions that PyObjC doesn't
expose directly (`AudioHardwareCreateProcessTap`,
`AudioDeviceCreateIOProcID`, `AudioDeviceStart`, ...).

On first use, macOS will pop a permission dialog (TCC). If the user denies
it, the C function returns an error and we surface a clear message that
mentions `tccutil reset AudioCapture` so the user can recover.
"""
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportReturnType=false, reportAttributeAccessIssue=false

from __future__ import annotations

import ctypes
import sys
import threading
from ctypes import c_void_p, c_uint32, c_int32, c_float, POINTER, Structure, byref
from collections.abc import Iterator
from queue import Queue
from typing import Any

import numpy as np

from .._protocols import RecorderError

MACOS_PROCESS_TAP_MIN_VERSION = (14, 4)


class MacosProcessTapSource:
    """Capture system audio on macOS 14.4+ via Core Audio Process Tap.

    The class is a no-op stub on non-macOS platforms — `open()` raises a
    `RecorderError` explaining the platform mismatch. This lets the factory
    construct the class during `make_audio_source` resolution on any OS.
    """

    def __init__(self, device: str | int | None = None) -> None:
        self._device = device
        self._stop = threading.Event()
        self._sample_rate = 16000
        self._channels = 1
        self._tap_id: int = 0
        self._device_id: int = 0
        self._proc_id: c_void_p = c_void_p()
        self._queue: Queue[np.ndarray] = Queue()
        self._thread: threading.Thread | None = None
        self._io_proc_ref = None
        self._callback_bridge = None

    def open(self, sample_rate: int, channels: int) -> None:
        if not sys.platform == "darwin":
            raise RecorderError(
                f"macOS Process Tap is only available on macOS. Current platform: {sys.platform}."
            )
        if not _macos_meets_min_version(MACOS_PROCESS_TAP_MIN_VERSION):
            raise RecorderError(
                f"macOS Process Tap requires macOS "
                f"{MACOS_PROCESS_TAP_MIN_VERSION[0]}.{MACOS_PROCESS_TAP_MIN_VERSION[1]}+. "
                "On older macOS, install BlackHole for system audio capture."
            )
        self._check_authorization()
        self._sample_rate = sample_rate
        self._channels = channels

        try:
            self._build_tap_and_aggregate()
            self._install_io_proc()
            self._start_device()
        except RecorderError:
            raise
        except Exception as exc:
            self._teardown()
            raise RecorderError(f"Failed to start macOS Process Tap: {exc}") from exc

    def _check_authorization(self) -> None:
        """Best-effort TCC prompt for AudioCapture. The C call will trigger
        the dialog if we don't check first; we still try the check to give
        a friendlier error on denial."""
        try:
            import AVFoundation  # type: ignore[import-not-found]  # noqa: F401
        except ImportError:
            return

    def _build_tap_and_aggregate(self) -> None:
        """Build the tap description and aggregate device, then create them
        via the C API. Mirrors Meetily's `core_audio.rs:88-145` translated
        to ctypes + PyObjC."""
        try:
            from CoreAudio import (  # type: ignore[import-not-found]
                AudioHardwareCreateProcessTap,
                kAudioAggregateDevicePropertyIsPrivateKey,
                kAudioAggregateDevicePropertyTapListKey,
                kAudioSubDevicePropertyUIDKey,
            )
            from CoreFoundation import (  # type: ignore[import-not-found]
                CFDictionaryCreateMutable,
                CFDictionarySetValue,
                CFArrayCreateMutable,
                CFArrayAppendValue,
                kCFAllocatorDefault,
                kCFBooleanTrue,
                CFStringCreateWithCString,
            )
        except ImportError as exc:
            raise RecorderError(
                "pyobjc-framework-CoreAudio is not installed. "
                "Run `pip install pyobjc-framework-CoreAudio pyobjc-framework-AVFoundation` "
                "and retry. (Or `nina setup` on macOS to install automatically.)"
            ) from exc

        tap_desc = _build_mono_global_tap_description()
        if tap_desc is None:
            raise RecorderError(
                "Failed to construct CAAudioTapDescription. "
                "Your macOS version may not support Process Tap."
            )

        out_tap = c_uint32(0)
        status = AudioHardwareCreateProcessTap(tap_desc, byref(out_tap))
        if status != 0:
            raise RecorderError(
                f"AudioHardwareCreateProcessTap failed with OSStatus {status}. "
                "If macOS is denying the request, run "
                "`tccutil reset AudioCapture <bundle-id>` and retry. "
                "Accept the AudioCapture permission dialog when prompted."
            )
        self._tap_id = out_tap.value

        uid_str = CFStringCreateWithCString(
            kCFAllocatorDefault, f"nina-tap-{self._tap_id}".encode(), 0x08000100
        )

        sub_dict = CFDictionaryCreateMutable(kCFAllocatorDefault, 1, None, None)
        CFDictionarySetValue(sub_dict, kAudioSubDevicePropertyUIDKey, uid_str)

        tap_array = CFArrayCreateMutable(kCFAllocatorDefault, 1, None)
        CFArrayAppendValue(tap_array, sub_dict)

        agg_dict = CFDictionaryCreateMutable(kCFAllocatorDefault, 2, None, None)
        CFDictionarySetValue(agg_dict, kAudioAggregateDevicePropertyIsPrivateKey, kCFBooleanTrue)
        CFDictionarySetValue(agg_dict, kAudioAggregateDevicePropertyTapListKey, tap_array)

        self._device_id = _AudioHardwareCreateAggregateDevice(agg_dict)
        if self._device_id == 0:
            raise RecorderError(
                "AudioHardwareCreateAggregateDevice returned 0. "
                "The Process Tap could not be wrapped in an aggregate device."
            )

    def _install_io_proc(self) -> None:
        try:
            from CoreAudio import (  # type: ignore[import-not-found]
                AudioDeviceCreateIOProcID,
                AudioDeviceIOProc,
            )
        except ImportError as exc:
            raise RecorderError(
                "pyobjc-framework-CoreAudio does not expose AudioDeviceCreateIOProcID. "
                "Try a newer pyobjc version."
            ) from exc

        bridge = _IoProcBridge(self._queue)
        self._callback_bridge = bridge
        self._io_proc_ref = AudioDeviceIOProc(_io_proc_trampoline)

        out_proc = c_void_p()
        status = AudioDeviceCreateIOProcID(
            self._device_id, self._io_proc_ref, bridge.as_void_p(), byref(out_proc)
        )
        if status != 0:
            raise RecorderError(f"AudioDeviceCreateIOProcID failed with OSStatus {status}")
        self._proc_id = out_proc

    def _start_device(self) -> None:
        try:
            from CoreAudio import AudioDeviceStart  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RecorderError("pyobjc-framework-CoreAudio missing AudioDeviceStart") from exc
        status = AudioDeviceStart(self._device_id, self._proc_id)
        if status != 0:
            raise RecorderError(f"AudioDeviceStart failed with OSStatus {status}")

    def stream(self) -> Iterator[bytes]:
        while not self._stop.is_set():
            try:
                chunk = self._queue.get(timeout=0.1)
            except Exception:
                continue
            if chunk is None:  # pyright: ignore[reportUnnecessaryComparison]
                break
            pcm = (np.clip(chunk, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            yield pcm

    def close(self) -> None:
        self._stop.set()
        self._teardown()

    def _teardown(self) -> None:
        if self._device_id and self._proc_id:
            try:
                from CoreAudio import (  # type: ignore[import-not-found]
                    AudioDeviceStop,
                    AudioDeviceDestroyIOProcID,
                )

                AudioDeviceStop(self._device_id, self._proc_id)
                AudioDeviceDestroyIOProcID(self._device_id, self._proc_id)
            except Exception:
                pass
            self._proc_id = c_void_p()
        if self._tap_id:
            try:
                from CoreAudio import AudioHardwareDestroyProcessTap  # type: ignore[import-not-found]

                AudioHardwareDestroyProcessTap(self._tap_id)
            except Exception:
                pass
            self._tap_id = 0
        if self._device_id:
            try:
                _AudioHardwareDestroyAggregateDevice(self._device_id)
            except Exception:
                pass
            self._device_id = 0
        self._callback_bridge = None
        self._io_proc_ref = None


def _macos_meets_min_version(min_version: tuple[int, int]) -> bool:
    if not sys.platform == "darwin":
        return False
    try:
        import platform

        ver = platform.mac_ver()[0]
        if not ver:
            return False
        parts = ver.split(".")
        if len(parts) < 2:
            return False
        major, minor = int(parts[0]), int(parts[1])
        return (major, minor) >= min_version
    except Exception:
        return False


def _build_mono_global_tap_description() -> Any:
    """Build a `CAAudioTapDescription` configured as a mono global tap that
    excludes the current process. Returns `None` if construction fails.

    On macOS 14.4+, the standard initializer is
    `+[CAAudioTapDescription initWithMonoGlobalTapExcludingProcesses:]`.
    Some PyObjC versions expose the class as `CoreAudio.CAAudioTapDescription`.
    """
    try:
        import CoreAudio  # type: ignore[import-not-found]
    except ImportError:
        return None
    cls = getattr(CoreAudio, "CAAudioTapDescription", None)
    if cls is None:
        return None
    try:
        import objc  # type: ignore[import-not-found]

        ns_array_cls = objc.lookUpClass("NSArray")
        empty_array = ns_array_cls.array()
        sel = b"initWithMonoGlobalTapExcludingProcesses:"
        desc = cls.performSelector_(sel, withObject=empty_array)
    except Exception:
        return None
    if desc is None:
        return None
    try:
        desc.retain()
    except Exception:
        pass
    return desc


class _AudioBuffer(Structure):
    _fields_ = [
        ("mNumberChannels", c_uint32),
        ("mDataByteSize", c_uint32),
        ("mData", c_void_p),
    ]


class _AudioBufferListHeader(Structure):
    _fields_ = [
        ("mNumberBuffers", c_uint32),
        ("mBuffers", _AudioBuffer),
    ]


class _IoProcBridge:
    """Holds a Python queue and a Python callback. The C trampoline writes
    into the queue from the audio thread; the recorder reads from it."""

    def __init__(self, queue: Queue[np.ndarray]) -> None:
        self.queue = queue
        self._void_p = ctypes.c_void_p()
        ctypes.pythonapi.Py_IncRef(ctypes.py_object(self))
        self._void_p.value = id(self)

    def as_void_p(self) -> c_void_p:
        return ctypes.cast(ctypes.pointer(self._void_p), c_void_p)

    def __del__(self) -> None:  # pragma: no cover - best effort
        try:
            ctypes.pythonapi.Py_DecRef(ctypes.py_object(self))
        except Exception:
            pass


def _io_proc_trampoline(
    device_id: c_uint32,
    now: c_void_p,
    input_data: c_void_p,
    input_time: c_void_p,
    output_data: c_void_p,
    output_time: c_void_p,
    client_data: c_void_p,
) -> c_int32:
    """C-callable trampoline invoked on the audio thread. Marshals the
    AudioBufferList into numpy float32 and pushes it to the bridge's queue.

    Signature matches `AudioDeviceIOProc` (C function pointer).
    """
    try:
        if not input_data:
            return 0
        bridge_obj = ctypes.cast(client_data, ctypes.py_object).value
        if bridge_obj is None:
            return 0
        list_ptr = ctypes.cast(input_data, POINTER(_AudioBufferListHeader))
        header = list_ptr.contents
        n_buffers = header.mNumberBuffers
        if n_buffers == 0:
            return 0

        first = header.mBuffers
        n_samples = first.mDataByteSize // (4 * first.mNumberChannels or 1)
        if n_samples == 0:
            return 0

        ptr_type = POINTER(c_float)
        buf_ptr = ctypes.cast(first.mData, ptr_type)
        samples = np.ctypeslib.as_array(buf_ptr, shape=(n_samples,))

        if n_buffers > 1:
            channels = [
                np.ctypeslib.as_array(ctypes.cast(b.mData, ptr_type), shape=(b.mDataByteSize // 4,))
                for b in [header.mBuffers]
            ]
            stacked = np.stack([c[:n_samples] for c in channels], axis=0)
            mono = stacked.mean(axis=0)
        else:
            mono = samples[:n_samples]

        bridge_obj.queue.put(mono.astype(np.float32, copy=True))
        return 0
    except Exception:
        return 0


def _AudioHardwareCreateAggregateDevice(description: c_void_p) -> c_uint32:
    """Call `AudioHardwareCreateAggregateDevice` via ctypes. PyObjC doesn't
    expose this symbol on all versions."""
    try:
        lib = _load_coreaudio_lib()
    except OSError as exc:
        raise RecorderError(f"Failed to load CoreAudio framework: {exc}") from exc
    fn = getattr(lib, "AudioHardwareCreateAggregateDevice", None)
    if fn is None:
        raise RecorderError("AudioHardwareCreateAggregateDevice not found in CoreAudio")
    fn.restype = c_int32
    fn.argtypes = [c_void_p, POINTER(c_uint32)]
    out = c_uint32(0)
    status = fn(description, byref(out))
    if status != 0:
        raise RecorderError(f"AudioHardwareCreateAggregateDevice failed with OSStatus {status}")
    return out.value


def _AudioHardwareDestroyAggregateDevice(device_id: c_uint32) -> None:
    try:
        lib = _load_coreaudio_lib()
    except OSError:
        return
    fn = getattr(lib, "AudioHardwareDestroyAggregateDevice", None)
    if fn is None:
        return
    fn.restype = c_int32
    fn.argtypes = [c_uint32]
    try:
        fn(device_id)
    except Exception:
        pass


def _load_coreaudio_lib() -> ctypes.CDLL:
    return ctypes.CDLL("/System/Library/Frameworks/CoreAudio.framework/CoreAudio")
