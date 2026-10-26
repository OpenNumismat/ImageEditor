"""Small, UI-independent wrapper around libgphoto2's C API."""

import ctypes
import copy
import atexit
import glob
import json
import os
import sys
import threading
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, TypedDict, Union

if TYPE_CHECKING:
    from PySide6.QtCore import QSettings


GP_WIDGET_WINDOW = 0
GP_WIDGET_SECTION = 1
GP_WIDGET_TEXT = 2
GP_WIDGET_RANGE = 3
GP_WIDGET_TOGGLE = 4
GP_WIDGET_RADIO = 5
GP_WIDGET_MENU = 6
GP_WIDGET_BUTTON = 7
GP_WIDGET_DATE = 8
GP_OPERATION_CAPTURE_IMAGE = 1
GP_OPERATION_CAPTURE_PREVIEW = 8
# CameraFileType values from gphoto2-file.h; the enum starts at PREVIEW, so
# GP_FILE_TYPE_NORMAL is 1, not 0. Passing 0 downloads the thumbnail instead
# of the image, which fails for freshly captured files that have no thumbnail.
GP_FILE_TYPE_PREVIEW = 0
GP_FILE_TYPE_NORMAL = 1
GP_FILE_TYPE_RAW = 2
# libgphoto2_port result code (gphoto2-port-result.h), reported by camera
# autodetection when not a single camera/port driver plugin could be loaded
# from the CAMLIBS/IOLIBS directories.
GP_ERROR_LIBRARY = -4

# Handles returned by os.add_dll_directory() must stay referenced for as long
# as the DLL search path is needed; garbage-collecting one removes its
# directory and can break lazy loading of libgphoto2 plugin dependencies.
_dll_directory_handles = []
_preloaded_dlls = []
# Each C runtime keeps its own copy of the environment; cached handles keep
# them alive and let _set_msys2_environment update every copy.
_crt_runtimes: Dict[str, ctypes.CDLL] = {}


def _crt(runtime: str) -> ctypes.CDLL:
    """Return a loaded C runtime by DLL name, caching the handle."""
    dll = _crt_runtimes.get(runtime)
    if dll is None:
        dll = ctypes.CDLL(runtime)
        _crt_runtimes[runtime] = dll
    return dll


# Opaque handle held by or returned from libgphoto2's C API. Functions whose
# ``restype`` is ``c_void_p`` return ``int`` (or ``None`` for NULL), while
# handles allocated locally are ``ctypes.c_void_p`` instances.
Handle = Union[int, ctypes.c_void_p]

# A single camera-setting value as read from or written to a config widget.
Value = Union[int, float, str, None]


class ConfigItem(TypedDict):
    """Metadata describing one flattened camera-configuration setting.

    ``range`` is ``None`` unless the item is a GP_WIDGET_RANGE whose bounds
    were readable, and ``value`` is ``None`` when libgphoto2 could not read
    the widget. Items persisted through QSettings make a JSON round trip,
    after which ``range`` arrives as a list instead of a tuple.
    """

    path: str
    name: str
    label: str
    type: int
    value: Value
    choices: List[str]
    readonly: bool
    range: Optional[Tuple[float, float, float]]


class Preferences(TypedDict, total=False):
    """Persisted per-camera capture settings.

    All keys are optional: ``save_preferences`` stores the full set, but a
    camera without saved preferences returns an empty dict, so readers must
    use ``.get(...)`` with defaults.
    """

    settings: Dict[str, Value]
    preview: bool
    restore_target: bool


class InspectResult(TypedDict):
    """Result of a live camera-configuration inspection."""

    parameters: List[ConfigItem]
    preview: bool
    capture: bool


class CameraAbilities(ctypes.Structure):
    """C-compatible libgphoto2 camera-driver capabilities structure."""

    _fields_ = [
        ("model", ctypes.c_char * 128), ("status", ctypes.c_int),
        ("port", ctypes.c_int), ("speed", ctypes.c_int * 64),
        ("operations", ctypes.c_int), ("file_operations", ctypes.c_int),
        ("folder_operations", ctypes.c_int), ("usb_vendor", ctypes.c_int),
        ("usb_product", ctypes.c_int), ("usb_class", ctypes.c_int),
        ("usb_subclass", ctypes.c_int), ("usb_protocol", ctypes.c_int),
        ("library", ctypes.c_char * 1024), ("id", ctypes.c_char * 1024),
        ("device_type", ctypes.c_int), ("reserved2", ctypes.c_int),
        ("reserved3", ctypes.c_int), ("reserved4", ctypes.c_int),
        ("reserved5", ctypes.c_int), ("reserved6", ctypes.c_int),
        ("reserved7", ctypes.c_int), ("reserved8", ctypes.c_int),
    ]


class CameraFilePath(ctypes.Structure):
    """C-compatible path returned by libgphoto2 after a capture."""

    _fields_ = [("name", ctypes.c_char * 128), ("folder", ctypes.c_char * 1024)]


_INSTALL_HINT = (
    "Camera capture is optional: packaged builds bundle the libgphoto2 runtime; "
    "when running from source install MSYS2 UCRT64 plus the package "
    "mingw-w64-ucrt-x86_64-gphoto2 to enable it (see README_libgphoto2.md)."
)

# Environment variable overriding the libgphoto2 runtime root, used to point
# builds at a specific runtime (e.g. the bundled one in packaging smoke tests).
_RUNTIME_ENV_VAR = "GPHOTO2_RUNTIME"


def _versioned_directory(path: str) -> str:
    """Choose the newest numeric-version subdirectory under ``path``."""
    versions = [
        name for name in os.listdir(path)
        if os.path.isdir(os.path.join(path, name))
        and all(part.isdigit() for part in name.split("."))
    ]
    if not versions:
        raise OSError(f"No libgphoto2 plugin directory found in {path}")
    versions.sort(key=lambda item: tuple(int(part) for part in item.split(".")))
    return os.path.join(path, versions[-1])


def _candidate_roots() -> List[str]:
    """Return libgphoto2 runtime roots to try, most specific first.

    A root is a directory with ``bin/`` (DLLs) and ``lib/libgphoto2*/<version>/``
    (camera-driver and port-driver plugins); the runtime bundled next to the
    executable and an MSYS2 UCRT64 prefix share this layout. The bundled root is
    preferred so packaged builds work on machines without MSYS2.
    """
    roots = []
    override = os.environ.get(_RUNTIME_ENV_VAR)
    if override:
        roots.append(override)
    # Frozen apps: sys._MEIPASS covers PyInstaller both with and without
    # contents_directory; Nuitka standalone puts data next to the executable.
    for base in (getattr(sys, "_MEIPASS", None),
                 os.path.dirname(os.path.abspath(sys.executable))):
        if base:
            roots.append(os.path.join(base, "libgphoto2"))
    roots.append(r"C:\msys64\ucrt64")
    return roots


def _runtime_paths() -> Tuple[str, str, str]:
    """Return the binary, camera-driver, and port-driver directories.

    Searches the ``%GPHOTO2_RUNTIME%`` override, a ``libgphoto2`` folder
    bundled next to the executable, then a system-wide MSYS2 UCRT64
    installation.
    """
    problems = []
    for root in _candidate_roots():
        binary_dir = os.path.join(root, "bin")
        try:
            camlibs = _versioned_directory(os.path.join(root, "lib", "libgphoto2"))
            iolibs = _versioned_directory(os.path.join(root, "lib", "libgphoto2_port"))
        except OSError as error:
            problems.append(str(error))
            continue
        if not glob.glob(os.path.join(binary_dir, "libgphoto2-*.dll")):
            problems.append(f"No libgphoto2 DLLs in {binary_dir}")
            continue
        return binary_dir, camlibs, iolibs
    raise OSError(
        "No usable libgphoto2 runtime. " + " / ".join(problems) + f". {_INSTALL_HINT}"
    )


def _dll_named(binary_dir: str, pattern: str, description: str) -> str:
    """Return the newest DLL in ``binary_dir`` matching ``pattern``."""
    matches = sorted(glob.glob(os.path.join(binary_dir, pattern)))
    if not matches:
        raise OSError(f"No {description} found in {binary_dir}. {_INSTALL_HINT}")
    return matches[-1]


def _short_path(path: str) -> Optional[str]:
    """Return the ASCII 8.3 short form of an existing path, when there is one.

    Short names hand a path to code that only understands narrow (ANSI)
    strings, such as the MSYS2 libgphoto2 runtime, without any code-page
    conversion. Returns ``None`` when Windows has no short name for the path
    (8.3 names can be disabled per volume) or when the short name is not
    plain ASCII.
    """
    get_short_path_name = ctypes.windll.kernel32.GetShortPathNameW
    get_short_path_name.argtypes = [
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
    ]
    get_short_path_name.restype = ctypes.c_uint
    buffer = ctypes.create_unicode_buffer(32768)
    length = get_short_path_name(path, buffer, len(buffer))
    if not length or length >= len(buffer):
        return None
    short = buffer.value
    return short if short.isascii() else None


def _narrow_path(path: str) -> bytes:
    """Encode a path for the ANSI-based C runtime of the MSYS2 libgphoto2.

    That runtime receives CAMLIBS/IOLIBS through ``_putenv`` and reads them
    back with narrow ``getenv()``, opening the plugin directories through
    ANSI Win32 APIs, so the bytes must use the process ANSI code page.
    ``os.fsencode`` sends UTF-8 instead, and any non-ASCII character in the
    install path then names a directory that does not exist: libgphoto2
    loads no port drivers and autodetection fails with "Error loading a
    library". Prefer the ASCII-only 8.3 form of the path, fall back to the
    ANSI code page, and report paths neither encoding can represent.
    """
    short = _short_path(path)
    if short:
        return short.encode("ascii")
    try:
        return path.encode("mbcs")
    except UnicodeEncodeError:
        raise OSError(
            f"Cannot hand the path {path} to libgphoto2: its characters cannot "
            "be represented in the system code page. Move OpenNumismat to a "
            "path written with characters from your system language "
            "(e.g. C:\\OpenNumismat) and try again."
        ) from None


def _getenv(name: str, runtime: str = "msvcrt.dll") -> Optional[bytes]:
    """Return an environment variable as a given C runtime sees it.

    Every C runtime keeps its own copy of the environment and the MSYS2
    libgphoto2 reads the ``msvcrt.dll`` one, so that view decides what the
    library does; diagnostics compare it with ``ucrtbase.dll``'s copy.
    """
    getenv = _crt(runtime).getenv
    getenv.argtypes = [ctypes.c_char_p]
    getenv.restype = ctypes.c_char_p
    return getenv(name.encode("ascii"))


def _set_msys2_environment(name: str, value: str) -> None:
    """Set a process environment variable for the MSYS2 libgphoto2 runtime.

    Every C runtime keeps its own copy of the environment, and the MSYS2
    libgphoto2 reads the ``msvcrt.dll`` copy, which is snapshotted when that
    runtime is loaded. Writing only to ``ucrtbase.dll`` leaves that snapshot
    untouched: in a frozen application msvcrt is loaded before this code
    runs, so libgphoto2 keeps using whatever the process inherited (or its
    compiled-in defaults) and reports "Error loading a library" on machines
    without a configured runtime. Update every runtime copy and the OS
    environment as well.
    """
    encoded = _narrow_path(value)
    for runtime in ("ucrtbase.dll", "msvcrt.dll"):
        putenv = _crt(runtime)._putenv
        putenv.argtypes = [ctypes.c_char_p]
        putenv.restype = ctypes.c_int
        # _putenv is the narrow (ANSI) API, so the value must go in as
        # ANSI-safe bytes - see _narrow_path for why os.fsencode is wrong.
        if putenv(name.encode("ascii") + b"=" + encoded) != 0:
            raise OSError(f"Could not set {name} for the {runtime} runtime")
    os.environ[name] = encoded.decode("mbcs")


def _load_libraries() -> Tuple[ctypes.CDLL, ctypes.CDLL]:
    """Load libgphoto2 and its port library for the current platform."""
    if sys.platform.startswith("win"):
        binary_dir, camlibs, iolibs = _runtime_paths()
        _dll_directory_handles.append(os.add_dll_directory(binary_dir))
        _set_msys2_environment("CAMLIBS", camlibs)
        _set_msys2_environment("IOLIBS", iolibs)
        # libgphoto2 loads its camlib and port-driver plugins at runtime with
        # plain LoadLibrary calls, and resolving a plugin's own dependencies
        # (usb1.dll needs libusb-1.0.dll) ignores os.add_dll_directory(): it
        # falls back to the process PATH. Outside an MSYS2 shell PATH usually
        # lacks the runtime bin folder, the usb1 port driver then fails to load
        # and autodetection silently reports zero cameras. Prepending the bin
        # folder to PATH and preloading the plugin dependencies makes plugin
        # loading independent of how the app was started. The preloaded
        # handles must stay referenced to keep the DLLs loaded. The PATH entry
        # uses the same ANSI-safe form as CAMLIBS/IOLIBS, so narrow-based
        # searches by the plugin loader see a path they can open.
        search_dir = _narrow_path(binary_dir).decode("mbcs")
        os.environ["PATH"] = search_dir + os.pathsep + os.environ.get("PATH", "")
        for dependency in (
            "libusb-1.0.dll",
            "libgcc_s_seh-1.dll",
            "libwinpthread-1.dll",
            "libltdl-7.dll",
        ):
            dependency_path = os.path.join(binary_dir, dependency)
            if os.path.isfile(dependency_path):
                _preloaded_dlls.append(ctypes.CDLL(dependency_path))
        try:
            return (
                ctypes.CDLL(_dll_named(binary_dir, "libgphoto2-*.dll", "libgphoto2 DLL")),
                ctypes.CDLL(_dll_named(binary_dir, "libgphoto2_port-*.dll", "libgphoto2 port DLL")),
            )
        except OSError as error:
            raise OSError(f"Could not load libgphoto2: {error}. {_INSTALL_HINT}") from error
    if sys.platform.startswith("linux"):
        try:
            return ctypes.CDLL("libgphoto2.so.6"), ctypes.CDLL("libgphoto2_port.so.12")
        except OSError:
            return ctypes.CDLL("libgphoto2.so"), ctypes.CDLL("libgphoto2_port.so")
    if sys.platform.startswith("darwin"):
        for directory in ("", "/opt/homebrew/lib", "/usr/local/lib"):
            try:
                gp = os.path.join(directory, "libgphoto2.6.dylib") if directory else "libgphoto2.6.dylib"
                port = os.path.join(directory, "libgphoto2_port.12.dylib") if directory else "libgphoto2_port.12.dylib"
                return ctypes.CDLL(gp), ctypes.CDLL(port)
            except OSError:
                continue
        raise OSError("Could not load libgphoto2 on macOS")
    raise OSError(f"Unsupported operating system: {sys.platform}")


def _configure_api(gp: ctypes.CDLL, port: ctypes.CDLL) -> None:
    """Declare ctypes argument and return types for used C functions."""
    p = ctypes.c_void_p
    i = ctypes.c_int
    gp.gp_context_new.restype = p
    gp.gp_context_unref.argtypes = [p]
    gp.gp_list_new.argtypes = [ctypes.POINTER(p)]
    gp.gp_list_free.argtypes = [p]
    gp.gp_list_count.argtypes = [p]
    gp.gp_list_count.restype = i
    for function in (gp.gp_list_get_name, gp.gp_list_get_value):
        function.argtypes = [p, i, ctypes.POINTER(ctypes.c_char_p)]
        function.restype = i
    gp.gp_camera_autodetect.argtypes = [p, p]
    gp.gp_camera_autodetect.restype = i
    gp.gp_result_as_string.argtypes = [i]
    gp.gp_result_as_string.restype = ctypes.c_char_p
    # gp_setting_get(char *id, char *key, char *value) writes the setting's
    # canonical name into a caller-provided buffer.
    gp.gp_setting_get.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
    gp.gp_setting_get.restype = i

    gp.gp_abilities_list_new.argtypes = [ctypes.POINTER(p)]
    gp.gp_abilities_list_load.argtypes = [p, p]
    gp.gp_abilities_list_lookup_model.argtypes = [p, ctypes.c_char_p]
    gp.gp_abilities_list_lookup_model.restype = i
    gp.gp_abilities_list_get_abilities.argtypes = [p, i, ctypes.POINTER(CameraAbilities)]
    gp.gp_abilities_list_free.argtypes = [p]
    port.gp_port_info_list_new.argtypes = [ctypes.POINTER(p)]
    port.gp_port_info_list_load.argtypes = [p]
    port.gp_port_info_list_lookup_path.argtypes = [p, ctypes.c_char_p]
    port.gp_port_info_list_lookup_path.restype = i
    port.gp_port_info_list_get_info.argtypes = [p, i, ctypes.POINTER(p)]
    port.gp_port_info_list_free.argtypes = [p]

    gp.gp_camera_new.argtypes = [ctypes.POINTER(p)]
    gp.gp_camera_set_abilities.argtypes = [p, CameraAbilities]
    gp.gp_camera_set_port_info.argtypes = [p, p]
    gp.gp_camera_init.argtypes = [p, p]
    gp.gp_camera_exit.argtypes = [p, p]
    gp.gp_camera_unref.argtypes = [p]
    gp.gp_camera_get_config.argtypes = [p, ctypes.POINTER(p), p]
    gp.gp_camera_set_config.argtypes = [p, p, p]
    gp.gp_camera_capture.argtypes = [p, i, ctypes.POINTER(CameraFilePath), p]
    gp.gp_camera_capture.restype = i
    gp.gp_camera_capture_preview.argtypes = [p, p, p]
    gp.gp_camera_capture_preview.restype = i
    gp.gp_camera_file_get.argtypes = [p, ctypes.c_char_p, ctypes.c_char_p, i, p, p]
    gp.gp_camera_file_delete.argtypes = [p, ctypes.c_char_p, ctypes.c_char_p, p]
    gp.gp_file_new.argtypes = [ctypes.POINTER(p)]
    gp.gp_file_free.argtypes = [p]
    gp.gp_file_get_data_and_size.argtypes = [p, ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_ulong)]
    gp.gp_widget_free.argtypes = [p]
    gp.gp_widget_get_child_by_name.argtypes = [p, ctypes.c_char_p, ctypes.POINTER(p)]
    gp.gp_widget_count_children.argtypes = [p]
    gp.gp_widget_count_children.restype = i
    gp.gp_widget_get_child.argtypes = [p, i, ctypes.POINTER(p)]
    gp.gp_widget_get_name.argtypes = [p, ctypes.POINTER(ctypes.c_char_p)]
    gp.gp_widget_get_label.argtypes = [p, ctypes.POINTER(ctypes.c_char_p)]
    gp.gp_widget_get_type.argtypes = [p, ctypes.POINTER(i)]
    gp.gp_widget_get_value.argtypes = [p, p]
    gp.gp_widget_set_value.argtypes = [p, p]
    gp.gp_widget_count_choices.argtypes = [p]
    gp.gp_widget_count_choices.restype = i
    gp.gp_widget_get_choice.argtypes = [p, i, ctypes.POINTER(ctypes.c_char_p)]
    gp.gp_widget_get_range.argtypes = [p, ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float)]
    gp.gp_widget_get_readonly.argtypes = [p, ctypes.POINTER(i)]


def _decode(value: Optional[bytes]) -> str:
    """Decode a nullable UTF-8 string returned by libgphoto2."""
    return value.decode("utf-8", errors="replace") if value else ""


def classify_capture_target(value: Value) -> Optional[bool]:
    """Classify a capture-target widget value: True = RAM, False = card.

    Returns ``None`` when the value cannot be classified: capture-target
    choices are gettext-translated labels, so keyword matching fails in
    some locales. Callers then fall back to the driver's canonical
    ``ptp2/capturetarget`` setting ("sdram"/"card") instead of guessing.
    """
    normalized = str(value).lower().strip()
    if "card" in normalized:
        return False
    if any(token in normalized for token in ("ram", "sdram", "internal")):
        return True
    return None


class LibGPhotoCamera:
    """Own the libgphoto2 libraries and perform camera/config/capture operations."""

    gp: ctypes.CDLL
    portlib: ctypes.CDLL

    def __init__(self) -> None:
        """Load libgphoto2 and prepare the ctypes API bindings."""
        self.gp, self.portlib = _load_libraries()
        _configure_api(self.gp, self.portlib)
        self.last_resolved_camera = None

    def _error(self, result: int, operation: str) -> RuntimeError:
        """Create a readable exception for a negative libgphoto2 result."""
        detail = _decode(self.gp.gp_result_as_string(result)) or f"error {result}"
        if result == GP_ERROR_LIBRARY:
            detail += ". " + self._plugin_diagnostics()
        return RuntimeError(f"{operation}: {detail}")

    def _plugin_diagnostics(self) -> str:
        """Explain a GP_ERROR_LIBRARY result with what the plugin loader saw.

        "Error loading a library" alone cannot distinguish its causes: the
        runtime resolving to the wrong root, plugin DLLs missing from their
        folder, present but refused by the OS (antivirus), or listing fine
        but failing to load again during detection. Probing the same inputs
        libgphoto2 uses turns a support round trip into an answer.
        """
        details = []
        try:
            binary_dir, camlibs, iolibs = _runtime_paths()
        except OSError as error:
            return f"{error}"
        details.append(f"runtime bin: {binary_dir}")
        for name in ("CAMLIBS", "IOLIBS"):
            value = _getenv(name)
            if value is None:
                details.append(f"{name} is not set")
                continue
            decoded = value.decode("mbcs", errors="replace")
            state = "exists" if os.path.isdir(decoded) else "MISSING"
            detail = f"{name}: {decoded} ({state})"
            other = _getenv(name, "ucrtbase.dll")
            if other != value:
                detail += f"; ucrtbase.dll sees {other!r}"
            details.append(detail)
        for label, directory in (("camlibs", camlibs), ("iolibs", iolibs)):
            dlls = sorted(glob.glob(os.path.join(directory, "*.dll")))
            broken = []
            for dll in dlls:
                try:
                    ctypes.CDLL(dll)
                except OSError as error:
                    broken.append(f"{os.path.basename(dll)}: {error}")
            if not dlls:
                state = "no plugin DLLs found"
            elif broken:
                state = "not loadable: " + "; ".join(broken)
            else:
                state = "all load"
            details.append(f"{label}: {len(dlls)} plugin DLL(s) in {directory}: {state}")
        # Ask libgphoto2 itself whether it can see any port drivers: a zero
        # count means the plugins were never found; a healthy count with this
        # error means one failed to load again while detection was running.
        port_list = ctypes.c_void_p()
        result = self.portlib.gp_port_info_list_new(ctypes.byref(port_list))
        if result >= 0:
            result = self.portlib.gp_port_info_list_load(port_list)
            if result < 0:
                details.append(
                    "libgphoto2 port driver scan failed ("
                    + _decode(self.gp.gp_result_as_string(result)) + ")"
                )
            else:
                count = self.portlib.gp_port_info_list_count(port_list)
                details.append(f"libgphoto2 port driver scan: {count} driver(s) seen")
            self.portlib.gp_port_info_list_free(port_list)
        return (
            "; ".join(details)
            + ". Antivirus software can refuse these unsigned DLLs; move "
            "OpenNumismat to a simple path such as C:\\OpenNumismat and check "
            "that the libgphoto2 folder sits next to OpenNumismat.exe."
        )

    def cameras(self) -> List[Dict[str, str]]:
        """Enumerate currently connected cameras as model/port records."""
        gp = self.gp
        context = gp.gp_context_new()
        if not context:
            raise RuntimeError("Could not create a libgphoto2 context")
        camera_list = ctypes.c_void_p()
        try:
            result = gp.gp_list_new(ctypes.byref(camera_list))
            if result < 0:
                raise self._error(result, "Could not create camera list")
            result = gp.gp_camera_autodetect(camera_list, context)
            if result < 0:
                raise self._error(result, "Camera detection failed")
            found = []
            for index in range(gp.gp_list_count(camera_list)):
                model, port = ctypes.c_char_p(), ctypes.c_char_p()
                gp.gp_list_get_name(camera_list, index, ctypes.byref(model))
                gp.gp_list_get_value(camera_list, index, ctypes.byref(port))
                found.append({"model": _decode(model.value), "port": _decode(port.value)})
            return found
        finally:
            if camera_list:
                gp.gp_list_free(camera_list)
            gp.gp_context_unref(context)

    def _close(self, opened: Tuple[Handle, Handle, int, Handle, Handle]) -> None:
        """Release all libgphoto2 resources associated with an open camera."""
        context, camera, _operations, port_list, abilities_list = opened
        gp = self.gp
        gp.gp_camera_exit(camera, context)
        gp.gp_camera_unref(camera)
        self.portlib.gp_port_info_list_free(port_list)
        gp.gp_abilities_list_free(abilities_list)
        gp.gp_context_unref(context)

    def _get_config(self, camera: Handle, context: Handle) -> Handle:
        """Fetch the camera's live configuration tree."""
        config = ctypes.c_void_p()
        result = self.gp.gp_camera_get_config(camera, ctypes.byref(config), context)
        if result < 0:
            if config:
                self.gp.gp_widget_free(config)
            raise self._error(result, "Could not read camera settings")
        return config

    def _read_value(self, widget: Handle, widget_type: int) -> Value:
        """Read a widget value using the C type required by its widget kind."""
        if widget_type in (GP_WIDGET_TOGGLE, GP_WIDGET_DATE):
            value = ctypes.c_int()
            result = self.gp.gp_widget_get_value(widget, ctypes.byref(value))
            if result < 0:
                return None
            return value.value
        if widget_type == GP_WIDGET_RANGE:
            value = ctypes.c_float()
            result = self.gp.gp_widget_get_value(widget, ctypes.byref(value))
            if result < 0:
                return None
            return value.value
        value = ctypes.c_char_p()
        result = self.gp.gp_widget_get_value(widget, ctypes.byref(value))
        return _decode(value.value) if result >= 0 else None

    def _config_items(
        self, widget: Handle, prefix: str = ""
    ) -> List[ConfigItem]:
        """Flatten a config subtree into path-addressed setting metadata."""
        gp = self.gp
        name = ctypes.c_char_p()
        label = ctypes.c_char_p()
        widget_type = ctypes.c_int()
        gp.gp_widget_get_name(widget, ctypes.byref(name))
        gp.gp_widget_get_label(widget, ctypes.byref(label))
        gp.gp_widget_get_type(widget, ctypes.byref(widget_type))
        own_name = _decode(name.value)
        path = f"{prefix}/{own_name}" if own_name else prefix
        kind = widget_type.value
        readonly = ctypes.c_int()
        gp.gp_widget_get_readonly(widget, ctypes.byref(readonly))

        items: List[ConfigItem] = []
        if kind not in (GP_WIDGET_WINDOW, GP_WIDGET_SECTION, GP_WIDGET_BUTTON) and path:
            value = self._read_value(widget, kind)
            choices = []
            if kind in (GP_WIDGET_RADIO, GP_WIDGET_MENU):
                for index in range(gp.gp_widget_count_choices(widget)):
                    choice = ctypes.c_char_p()
                    if gp.gp_widget_get_choice(widget, index, ctypes.byref(choice)) >= 0:
                        choices.append(_decode(choice.value))
            value_range: Optional[Tuple[float, float, float]] = None
            if kind == GP_WIDGET_RANGE:
                low, high, step = ctypes.c_float(), ctypes.c_float(), ctypes.c_float()
                if gp.gp_widget_get_range(widget, ctypes.byref(low), ctypes.byref(high), ctypes.byref(step)) >= 0:
                    value_range = (low.value, high.value, step.value)
            items.append({
                "path": path, "name": own_name,
                "label": _decode(label.value) or own_name,
                "type": kind, "value": value, "choices": choices,
                "readonly": bool(readonly.value),
                "range": value_range,
            })

        for index in range(gp.gp_widget_count_children(widget)):
            child = ctypes.c_void_p()
            if gp.gp_widget_get_child(widget, index, ctypes.byref(child)) >= 0:
                items.extend(self._config_items(child, path))
        return items

    def inspect(self, selected: Dict[str, str]) -> InspectResult:
        """Return live config metadata and advertised capture capabilities."""
        opened, config = self._open_and_config(selected)
        try:
            context, camera, operations, *_ = opened
            parameters = self._config_items(config)
            target = next(
                (item for item in parameters if item["path"].endswith("/capturetarget")),
                None,
            )
            ram_available = bool(
                target and (
                    any(classify_capture_target(choice) is True for choice in target["choices"])
                    or self._target_is_ram_value(target["value"])
                )
            )
            return {
                "parameters": parameters,
                "preview": bool(operations & GP_OPERATION_CAPTURE_PREVIEW),
                "capture": bool(operations & GP_OPERATION_CAPTURE_IMAGE) and ram_available,
            }
        finally:
            self.gp.gp_widget_free(config)
            self._close(opened)

    def _open_and_config(
        self, selected: Dict[str, str]
    ) -> Tuple[Tuple[Handle, Handle, int, Handle, Handle], Handle]:
        """Connect and read live config, re-enumerating once if needed.

        The stored port for a selection can go stale between discovery and
        connection (replug, sleep). On failure the cameras are re-detected
        once and the retry uses an exact model/port match, or the single
        discovered camera of the same model. ``last_resolved_camera``
        records the identity that actually connected so the manager can
        re-key its cached state.
        """
        candidate = selected
        last_error = None
        for attempt in range(2):
            opened = None
            config = None
            try:
                opened = self._open_resources(candidate)
                config = self._get_config(opened[1], opened[0])
                self.last_resolved_camera = copy.deepcopy(candidate)
                return opened, config
            except Exception as error:
                last_error = error
                if config:
                    self.gp.gp_widget_free(config)
                if opened:
                    self._close(opened)
                if attempt:
                    break
                try:
                    discovered = self.cameras()
                except Exception as discovery_error:
                    last_error = discovery_error
                    break
                exact = [item for item in discovered if self._identity(item) == self._identity(selected)]
                same_model = [item for item in discovered if item.get("model") == selected.get("model")]
                if exact:
                    candidate = exact[0]
                elif len(same_model) == 1:
                    candidate = same_model[0]
                else:
                    break
        raise last_error or RuntimeError("Could not connect to camera")

    @staticmethod
    def _identity(camera: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Return the model/port identity used to match a discovered camera."""
        return camera.get("model"), camera.get("port")

    def _open_resources(
        self, selected: Dict[str, str]
    ) -> Tuple[Handle, Handle, int, Handle, Handle]:
        """Create, configure, and initialize a camera and its C resources."""
        gp, pl = self.gp, self.portlib
        context = gp.gp_context_new()
        if not context:
            raise RuntimeError("Could not create a libgphoto2 context")
        camera = ctypes.c_void_p()
        abilities_list = ctypes.c_void_p()
        port_list = ctypes.c_void_p()
        initialized = False
        try:
            for result, operation in (
                (gp.gp_camera_new(ctypes.byref(camera)), "Could not create camera"),
                (gp.gp_abilities_list_new(ctypes.byref(abilities_list)), "Could not create camera abilities list"),
            ):
                if result < 0:
                    raise self._error(result, operation)
            result = gp.gp_abilities_list_load(abilities_list, context)
            if result < 0:
                raise self._error(result, "Could not load camera abilities")
            index = gp.gp_abilities_list_lookup_model(abilities_list, selected["model"].encode())
            if index < 0:
                raise self._error(index, f"Unsupported camera model: {selected['model']}")
            abilities = CameraAbilities()
            result = gp.gp_abilities_list_get_abilities(abilities_list, index, ctypes.byref(abilities))
            if result < 0:
                raise self._error(result, "Could not read camera abilities")
            result = gp.gp_camera_set_abilities(camera, abilities)
            if result < 0:
                raise self._error(result, "Could not configure camera model")
            result = pl.gp_port_info_list_new(ctypes.byref(port_list))
            if result < 0:
                raise self._error(result, "Could not create camera port list")
            result = pl.gp_port_info_list_load(port_list)
            if result < 0:
                raise self._error(result, "Could not load camera ports")
            index = pl.gp_port_info_list_lookup_path(port_list, selected["port"].encode())
            if index < 0:
                raise self._error(index, f"Camera port is unavailable: {selected['port']}")
            port_info = ctypes.c_void_p()
            result = pl.gp_port_info_list_get_info(port_list, index, ctypes.byref(port_info))
            if result < 0:
                raise self._error(result, "Could not read camera port information")
            result = gp.gp_camera_set_port_info(camera, port_info)
            if result < 0:
                raise self._error(result, "Could not configure camera port")
            result = gp.gp_camera_init(camera, context)
            if result < 0:
                raise self._error(result, "Could not connect to camera")
            initialized = True
            return context, camera, abilities.operations, port_list, abilities_list
        except Exception:
            if initialized:
                gp.gp_camera_exit(camera, context)
            if camera:
                gp.gp_camera_unref(camera)
            if port_list:
                pl.gp_port_info_list_free(port_list)
            if abilities_list:
                gp.gp_abilities_list_free(abilities_list)
            if context:
                gp.gp_context_unref(context)
            raise

    def _find_widget(self, root: Handle, path: str) -> Handle:
        """Find a setting widget by its slash-delimited config path."""
        widget = root
        for segment in path.strip("/").split("/"):
            child = ctypes.c_void_p()
            result = self.gp.gp_widget_get_child_by_name(widget, segment.encode(), ctypes.byref(child))
            if result < 0:
                raise RuntimeError(f"Camera setting no longer exists: {path}")
            widget = child
        return widget

    def _set_value(self, widget: Handle, kind: int, value: Value) -> None:
        """Set a widget using a correctly typed temporary C value.

        ``None`` is not a settable value: numeric widget kinds raise
        ``TypeError`` from ``int(None)``/``float(None)`` and string kinds
        would send the literal text ``"None"`` to the camera. Callers
        replaying recorded originals must skip values that could not be
        read back when they were recorded.
        """
        if kind in (GP_WIDGET_TOGGLE, GP_WIDGET_DATE):
            converted = ctypes.c_int(int(value))
            pointer = ctypes.byref(converted)
        elif kind == GP_WIDGET_RANGE:
            converted = ctypes.c_float(float(value))
            pointer = ctypes.byref(converted)
        else:
            converted = ctypes.create_string_buffer(str(value).encode("utf-8"))
            pointer = ctypes.cast(converted, ctypes.c_void_p)
        result = self.gp.gp_widget_set_value(widget, pointer)
        if result < 0:
            raise self._error(result, "Could not set camera configuration")

    def _bytes_from_file(self, camera_file: Handle) -> bytes:
        """Copy image bytes from a libgphoto2 file object."""
        data, size = ctypes.c_char_p(), ctypes.c_ulong()
        result = self.gp.gp_file_get_data_and_size(camera_file, ctypes.byref(data), ctypes.byref(size))
        if result < 0:
            raise self._error(result, "Could not read image data")
        if not data or not size.value:
            raise RuntimeError("Camera returned an empty image")
        return ctypes.string_at(data, size.value)

    def _driver_capture_target(self) -> str:
        """Read the driver's canonical capture-target name ("sdram"/"card").

        For Nikon, Canon and Panasonic the "Capture Target" widget is just
        a view of the gphoto2 setting ``ptp2/capturetarget``; an unset key
        means "sdram", mirroring the driver's own default.
        """
        buffer = ctypes.create_string_buffer(1024)
        if self.gp.gp_setting_get(b"ptp2", b"capturetarget", buffer) < 0:
            return "sdram"
        return _decode(buffer.value) or "sdram"

    def _target_is_ram_value(self, value: Value) -> bool:
        """Return whether a capture-target value means internal memory.

        Unclassifiable (translated) labels fall back to the driver's
        canonical setting. Sony's untranslated "sdram"/"card"/"card+sdram"
        values always classify directly and never reach the fallback.
        """
        classification = classify_capture_target(value)
        if classification is not None:
            return classification
        return self._driver_capture_target() == "sdram"

    @staticmethod
    def _is_volatile_capture_folder(folder: bytes) -> bool:
        """Return whether a captured file lives in camera RAM, not on a card.

        The ptp2 driver names RAM captures after the virtual root "/" or
        the synthetic "/store_XXXXXXXX" folder it fabricates, while real
        card files carry deeper paths like "/store_00010001/DCIM/100CANON".
        """
        segments = folder.decode("ascii", "replace").rstrip("/").split("/")
        return segments == [""] or (len(segments) == 2 and segments[1].startswith("store_"))

    def _rejected_settings(
        self,
        camera: Handle,
        context: Handle,
        changes: List[Tuple[str, ConfigItem, Value]],
        result: int,
    ) -> RuntimeError:
        """Explain which changed settings the camera refused to accept.

        A whole-tree ``gp_camera_set_config`` failure reports only one
        generic result code; re-applying each change on its own fresh tree
        identifies the rejected ones so the message can name them. A change
        accepted alone stays applied to the camera; if every change succeeds
        alone, the original error is reported unchanged.
        """
        rejected: List[str] = []
        for path, item, value in changes:
            reason = None
            tree = None
            try:
                tree = self._get_config(camera, context)
                widget = self._find_widget(tree, path)
                self._set_value(widget, item["type"], value)
                single = self.gp.gp_camera_set_config(camera, tree, context)
                if single < 0:
                    reason = _decode(self.gp.gp_result_as_string(single)) or f"error {single}"
            except Exception as error:
                reason = str(error)
            finally:
                if tree:
                    self.gp.gp_widget_free(tree)
            if reason is not None:
                rejected.append(f"{item['label']} ({path}): {reason}")
        if not rejected:
            return self._error(result, "Camera rejected configuration")
        return RuntimeError(
            "Camera rejected configuration - "
            + "; ".join(rejected)
            + ". Clear or change these settings and try again."
        )

    def capture(
        self,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        preview: bool = False,
    ) -> bytes:
        """Apply config values, then return captured image bytes."""
        return self._capture(selected, settings, preview, {}, True)

    def _capture(
        self,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        preview: bool,
        originals: Dict[str, Value],
        restore_target: bool,
    ) -> bytes:
        """Apply supported settings, enforce RAM safety, and capture an image.

        Standard (non-preview) captures never write to the camera card: the
        capture target is forced to internal RAM, the camera must confirm
        RAM targeting after the configuration push, and the captured file
        is downloaded and then deleted from the camera. Preview captures
        skip all of this because they do not touch the camera filesystem.
        """
        opened, config = self._open_and_config(selected)
        context, camera, operations, *_ = opened
        original_target = None
        target_path = None
        try:
            required_operation = (
                GP_OPERATION_CAPTURE_PREVIEW if preview else GP_OPERATION_CAPTURE_IMAGE
            )
            if not operations & required_operation:
                mode = "preview" if preview else "standard"
                raise RuntimeError(f"This camera does not support {mode} capture")
            parameters = self._config_items(config)
            live = {item["path"]: item for item in parameters}
            target_item = next((item for item in parameters if item["path"].endswith("/capturetarget")), None)
            if not preview:
                if not target_item:
                    raise RuntimeError("This camera has no capture-target setting; refusing standard capture to avoid writing to its card.")
                original_target = target_item["value"]
                target_path = target_item["path"]

            changes: List[Tuple[str, ConfigItem, Value]] = []
            for path, value in settings.items():
                item = live.get(path)
                if item is None or item["readonly"]:
                    continue
                # The capture target is owned exclusively by the RAM-safety
                # block below; persisted user settings must not change it.
                if path == target_path:
                    continue
                if item["choices"] and str(value) not in item["choices"]:
                    continue
                if item.get("range"):
                    low, high, _step = item["range"]
                    try:
                        value = max(low, min(high, float(value)))
                    except (TypeError, ValueError):
                        continue
                if value == item["value"]:
                    continue
                # A None original means the live value could not be read;
                # recording it would make restore() replay an unsettable
                # value, so leave this path out of the snapshot.
                if item["value"] is not None:
                    originals.setdefault(path, item["value"])
                widget = self._find_widget(config, path)
                self._set_value(widget, item["type"], value)
                changes.append((path, item, value))

            if not preview:
                target_widget = self._find_widget(config, target_path)
                target_value = self._read_value(target_widget, target_item["type"])
                if not self._target_is_ram_value(target_value):
                    # Write only a RAM choice we can name with certainty: a
                    # translated label we cannot classify is unusable, and
                    # guessing could capture to the user's card.
                    choices = self._choices(target_widget)
                    ram = next(
                        (choice for choice in choices if classify_capture_target(choice) is True),
                        None,
                    )
                    if ram is None:
                        raise RuntimeError("This camera does not offer an internal-RAM target; refusing to capture to its card.")
                    if target_item["readonly"]:
                        raise RuntimeError("Camera capture target is read-only and is not internal RAM; refusing standard capture.")
                    if original_target is not None:
                        originals.setdefault(target_path, original_target)
                    self._set_value(target_widget, target_item["type"], ram)
                    changes.append((target_path, target_item, ram))

            if changes:
                result = self.gp.gp_camera_set_config(camera, config, context)
                if result < 0:
                    raise self._rejected_settings(camera, context, changes, result)

            if not preview:
                # Re-read after applying config to confirm the camera accepted RAM.
                verified_config = self._get_config(camera, context)
                try:
                    verified_target = self._find_widget(verified_config, target_path)
                    verified_type = ctypes.c_int()
                    self.gp.gp_widget_get_type(verified_target, ctypes.byref(verified_type))
                    if not self._target_is_ram_value(self._read_value(verified_target, verified_type.value)):
                        raise RuntimeError("Camera did not confirm internal-RAM targeting; refusing standard capture.")
                finally:
                    self.gp.gp_widget_free(verified_config)

            if preview:
                camera_file = ctypes.c_void_p()
                result = self.gp.gp_file_new(ctypes.byref(camera_file))
                if result < 0:
                    raise self._error(result, "Could not create preview image buffer")
                try:
                    result = self.gp.gp_camera_capture_preview(camera, camera_file, context)
                    if result < 0:
                        raise self._error(result, "Camera preview capture failed")
                    return self._bytes_from_file(camera_file)
                finally:
                    self.gp.gp_file_free(camera_file)

            path = CameraFilePath()
            result = self.gp.gp_camera_capture(camera, 0, ctypes.byref(path), context)
            if result < 0:
                raise self._error(result, "Camera capture failed")
            folder = bytes(path.folder).split(b"\0", 1)[0]
            name = bytes(path.name).split(b"\0", 1)[0]
            if not folder or not name:
                raise RuntimeError("Camera capture returned an empty file path")
            camera_file = ctypes.c_void_p()
            result = self.gp.gp_file_new(ctypes.byref(camera_file))
            if result < 0:
                raise self._error(result, "Could not create image buffer")
            downloaded = False
            try:
                result = self.gp.gp_camera_file_get(camera, folder, name, GP_FILE_TYPE_NORMAL, camera_file, context)
                if result < 0:
                    raise self._error(result, "Could not retrieve captured image")
                image = self._bytes_from_file(camera_file)
                downloaded = True
                return image
            finally:
                self.gp.gp_file_free(camera_file)
                # Delete only after the bytes are safely in hand, and only
                # from camera RAM: a failed download would leave the photo's
                # only copy here, and a card file must never be deleted.
                if downloaded and self._is_volatile_capture_folder(folder):
                    self.gp.gp_camera_file_delete(camera, folder, name, context)
        finally:
            if config:
                if restore_target and original_target is not None:
                    try:
                        target_widget = self._find_widget(config, target_path)
                        current = self._read_value(target_widget, target_item["type"])
                        if current != original_target:
                            self._set_value(target_widget, target_item["type"], original_target)
                            self.gp.gp_camera_set_config(camera, config, context)
                    except Exception:
                        pass
                self.gp.gp_widget_free(config)
            self._close(opened)

    def capture_managed(
        self,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        originals: Dict[str, Value],
        preview: bool = False,
        restore_target: bool = True,
    ) -> bytes:
        """Capture while recording original values for manager cleanup."""
        return self._capture(selected, settings, preview, originals, restore_target)

    def restore(self, selected: Dict[str, str], values: Dict[str, Value]) -> None:
        """Best-effort apply saved original values to a camera's live config."""
        if not values:
            return
        opened, config = self._open_and_config(selected)
        context, camera, *_ = opened
        try:
            live = {item["path"]: item for item in self._config_items(config)}
            changed = False
            for path, value in values.items():
                if value is None:
                    # The original could not be read when it was recorded;
                    # there is nothing valid to write back.
                    continue
                item = live.get(path)
                if item is None or item["readonly"] or item["value"] == value:
                    continue
                if item["choices"] and str(value) not in item["choices"]:
                    continue
                widget = self._find_widget(config, path)
                self._set_value(widget, item["type"], value)
                changed = True
            if changed:
                result = self.gp.gp_camera_set_config(camera, config, context)
                if result < 0:
                    raise self._error(result, "Could not restore camera settings")
        finally:
            self.gp.gp_widget_free(config)
            self._close(opened)

    def _choices(self, widget: Handle) -> List[str]:
        """Return the current string choices advertised by a widget."""
        choices = []
        for index in range(self.gp.gp_widget_count_choices(widget)):
            choice = ctypes.c_char_p()
            if self.gp.gp_widget_get_choice(widget, index, ctypes.byref(choice)) >= 0:
                choices.append(_decode(choice.value))
        return choices


class LibGPhotoCameraManager:
    """Manage live camera state and persist per-camera config/preferences.

    Every public method serializes on ``_lock``, which is deliberately held
    across blocking camera I/O: a background capture and GUI-thread calls
    (inspect, re-evaluate, save) can share one manager safely, and the
    non-thread-safe ``LibGPhotoCamera`` is never touched from two threads
    at once. GUI-thread callers should therefore expect to block while a
    capture is in progress.
    """

    _SETTINGS_KEY = "libgphoto2/state"

    def __init__(
        self,
        camera_api: Optional[LibGPhotoCamera] = None,
        settings: Optional["QSettings"] = None,
    ) -> None:
        """Create a manager, optionally with test API and settings adapters."""
        self._camera_api = camera_api
        self._settings = settings
        self._cameras = None
        self._metadata = {}
        self._persisted_metadata = set()
        self._preferences = {}
        self._original_values = {}
        self._selected = {}
        self._lock = threading.RLock()
        self._load_persisted_state()

    @staticmethod
    def camera_key(camera: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        """Return the stable identity tuple for a camera record."""
        return LibGPhotoCamera._identity(camera)

    @property
    def last_camera(self) -> Optional[Dict[str, str]]:
        """Return a copy of the most recently selected camera, if any."""
        return copy.deepcopy(self._selected.get("last"))

    def availability_error(self) -> Optional[str]:
        """Return why the libgphoto2 runtime is unusable, or None if it loaded.

        Callers on machines without a libgphoto2 install use this to report
        the missing runtime only when camera capture is actually requested.
        """
        with self._lock:
            try:
                self._api()
            except Exception as error:
                return str(error)
        return None

    def _api(self) -> LibGPhotoCamera:
        """Lazily construct and return the low-level camera API wrapper."""
        if self._camera_api is None:
            self._camera_api = LibGPhotoCamera()
        return self._camera_api

    def _settings_store(self) -> Optional["QSettings"]:
        """Return the injected or application-default QSettings instance."""
        if self._settings is None:
            try:
                from PySide6.QtCore import QSettings
            except ImportError:
                return None
            self._settings = QSettings()
        return self._settings

    def _load_persisted_state(self) -> None:
        """Load saved preferences and config metadata, ignoring invalid data."""
        settings = self._settings_store()
        if settings is None:
            return
        try:
            raw_state = settings.value(self._SETTINGS_KEY, "")
            if not raw_state:
                return
            state = json.loads(str(raw_state))
            if state.get("version") != 1:
                return
            for entry in state.get("preferences", []):
                key = tuple(entry["camera"])
                self._preferences[key] = entry["value"]
            for entry in state.get("metadata", []):
                key = tuple(entry["camera"])
                self._metadata[key] = entry["value"]
                self._persisted_metadata.add(key)
            for entry in state.get("selected", []):
                key = tuple(entry["camera"])
                self._selected[key] = entry["value"]
            last_camera = state.get("last_camera")
            if last_camera:
                self._selected["last"] = last_camera
        except (AttributeError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            # Invalid or old state should not prevent camera use.
            self._metadata.clear()
            self._persisted_metadata.clear()
            self._preferences.clear()
            self._selected.clear()

    def _persist_state(self) -> None:
        """Write current preferences, metadata, and selection to QSettings."""
        settings = self._settings_store()
        if settings is None:
            return
        state = {
            "version": 1,
            "preferences": [
                {"camera": list(key), "value": value}
                for key, value in self._preferences.items()
            ],
            "metadata": [
                {"camera": list(key), "value": value}
                for key, value in self._metadata.items()
            ],
            "selected": [
                {"camera": list(key), "value": value}
                for key, value in self._selected.items()
                if key != "last"
            ],
            "last_camera": self._selected.get("last"),
        }
        try:
            settings.setValue(
                self._SETTINGS_KEY,
                json.dumps(state, ensure_ascii=False, allow_nan=False),
            )
        except (TypeError, ValueError):
            # Keep the in-memory preferences even if a camera exposes a value
            # that cannot be represented in the persistent JSON cache.
            return

    def cameras(self, refresh: bool = False) -> List[Dict[str, str]]:
        """Return detected cameras, optionally refreshing the discovery cache."""
        with self._lock:
            if refresh or self._cameras is None:
                self._cameras = copy.deepcopy(self._api().cameras())
            return copy.deepcopy(self._cameras)

    def inspect(
        self, selected: Dict[str, str], refresh: bool = False
    ) -> Dict[str, Any]:
        """Return cached config metadata or refresh it from the selected camera."""
        key = self.camera_key(selected)
        with self._lock:
            needs_live_inspection = refresh or key not in self._metadata or key in self._persisted_metadata
            if needs_live_inspection:
                try:
                    api = self._api()
                    api.last_resolved_camera = None
                    self._metadata[key] = api.inspect(selected)
                    self._persisted_metadata.discard(key)
                    self._adopt_resolved_camera(key, selected)
                    self._persist_state()
                except Exception:
                    if key not in self._persisted_metadata:
                        raise
                    # Saved schemas can keep the controls useful while a
                    # camera is asleep or temporarily unreachable. They are
                    # marked as cached so the UI will not offer capture.
                    cached = copy.deepcopy(self._metadata[key])
                    cached["_cached"] = True
                    return cached
            return copy.deepcopy(self._metadata.get(self.camera_key(selected), {}))

    def preferences(self, selected: Dict[str, str]) -> Preferences:
        """Return a deep copy of preferences saved for a camera.

        A camera without saved preferences yields an empty dict; because
        every ``Preferences`` key is optional, callers must read entries
        via ``.get(...)`` with defaults rather than indexing directly.
        """
        with self._lock:
            return copy.deepcopy(self._preferences.get(self.camera_key(selected), {}))

    def save_preferences(
        self,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        preview: bool,
        restore_target: bool,
    ) -> None:
        """Save setting values and capture options for a camera."""
        key = self.camera_key(selected)
        with self._lock:
            self._preferences[key] = {
                "settings": copy.deepcopy(settings),
                "preview": bool(preview),
                "restore_target": bool(restore_target),
            }
            self._selected["last"] = copy.deepcopy(selected)
            self._selected[key] = copy.deepcopy(selected)
            self._persist_state()

    def reset_preferences(self, selected: Dict[str, str]) -> None:
        """Forget a camera's saved values and cached configuration schema.

        The next inspection re-reads the camera's live configuration, so the
        dialog can reload the camera's own current settings. gphoto2 exposes
        no factory defaults - a config tree carries only each setting's
        current value and allowed choices - so "reset" means returning to the
        values the camera itself reports now.
        """
        key = self.camera_key(selected)
        with self._lock:
            self._preferences.pop(key, None)
            self._metadata.pop(key, None)
            self._persisted_metadata.discard(key)
            self._persist_state()

    def capture(
        self,
        selected: Dict[str, str],
        settings: Dict[str, Value],
        preview: bool = False,
        restore_target: bool = True,
    ) -> bytes:
        """Capture with the manager's original-value restoration tracking."""
        key = self.camera_key(selected)
        with self._lock:
            self._selected["last"] = copy.deepcopy(selected)
            self._selected[key] = copy.deepcopy(selected)
            originals = self._original_values.setdefault(key, {})
            api = self._api()
            api.last_resolved_camera = None
            try:
                image = api.capture_managed(
                    selected, settings, originals, preview, restore_target
                )
            finally:
                self._adopt_resolved_camera(key, selected, originals)
            current = self._preferences.setdefault(key, {})
            current.update({
                "settings": copy.deepcopy(settings),
                "preview": bool(preview),
                "restore_target": bool(restore_target),
            })
            # _adopt_resolved_camera() may have moved this camera's cached
            # state to the identity discovered during capture and updated
            # `selected` in place; re-file the preferences saved above under
            # that resolved identity so no stale key is left behind.
            resolved_key = self.camera_key(selected)
            if resolved_key != key:
                self._preferences[resolved_key] = self._preferences.pop(key)
            self._persist_state()
            return image

    def _adopt_resolved_camera(
        self,
        old_key: Tuple[Optional[str], Optional[str]],
        selected: Dict[str, str],
        originals: Optional[Dict[str, Value]] = None,
    ) -> None:
        """Move cached state to a camera identity resolved after re-enumeration."""
        resolved = getattr(self._camera_api, "last_resolved_camera", None)
        if not resolved:
            return
        new_key = self.camera_key(resolved)
        if new_key == old_key:
            return
        if isinstance(selected, dict):
            selected.update(resolved)
        self._selected.pop(old_key, None)
        self._selected[new_key] = copy.deepcopy(resolved)
        self._selected["last"] = copy.deepcopy(resolved)
        if old_key in self._preferences:
            self._preferences.setdefault(new_key, self._preferences[old_key])
            self._preferences.pop(old_key, None)
        if old_key in self._metadata:
            self._metadata.setdefault(new_key, self._metadata[old_key])
            self._metadata.pop(old_key, None)
        old_originals = self._original_values.pop(old_key, {})
        if originals is not None:
            old_originals.update(originals)
        if old_originals:
            new_originals = self._original_values.setdefault(new_key, {})
            for path, value in old_originals.items():
                new_originals.setdefault(path, value)

    def reevaluate(self) -> List[Dict[str, str]]:
        """Best-effort restore, then refresh camera and config discovery."""
        with self._lock:
            self._restore_all()
            self._metadata.clear()
            self._persisted_metadata.clear()
            self._cameras = None
            self._persist_state()
            return self.cameras(refresh=True)

    def release_camera(self, selected: Dict[str, str]) -> None:
        """Restore this camera's original values and forget its change snapshot."""
        key = self.camera_key(selected)
        with self._lock:
            values = self._original_values.get(key)
            if not values:
                return
            # If restore() raises, the snapshot is kept so a later release
            # or shutdown can retry.
            self._api().restore(selected, values)
            self._original_values.pop(key, None)

    def _restore_all(self) -> None:
        """Best-effort restore all settings changed during this process."""
        if self._camera_api is None:
            return
        pending = {}
        for key, values in list(self._original_values.items()):
            selected = self._selected.get(key)
            if not selected or not values:
                continue
            try:
                self._camera_api.restore(selected, values)
            except Exception:
                # The camera may be disconnected or asleep; cleanup is best-effort.
                pending[key] = values
        self._original_values = pending

    def close(self) -> None:
        """Restore camera settings and flush persistent application settings."""
        with self._lock:
            self._restore_all()
            settings = self._settings_store()
            if settings is not None and hasattr(settings, "sync"):
                settings.sync()


_default_manager = None
_default_manager_lock = threading.Lock()


def get_default_camera_manager() -> LibGPhotoCameraManager:
    """Return the lazily-created manager shared by dialogs in this process."""
    global _default_manager
    with _default_manager_lock:
        if _default_manager is None:
            _default_manager = LibGPhotoCameraManager()
        return _default_manager


def _close_default_manager() -> None:
    """Restore camera state held by the process-wide default manager."""
    if _default_manager is not None:
        _default_manager.close()


atexit.register(_close_default_manager)
