#!/usr/bin/env python3
"""Smoke test for a bundled libgphoto2 runtime.

Verifies that a packaged build works with the ``libgphoto2`` folder copied into
its dist directory and without any MSYS2 installation being picked up:

    python misc/test_gphoto2_bundle.py <target-dist-dir>

Checks, in order:

1. the loader resolves the runtime root to the bundle (%GPHOTO2_RUNTIME%);
2. the core libraries load from inside the bundle;
3. every bundled camlib/iolib plugin DLL loads (catches missing runtime
   dependencies such as libjpeg or libusb that only surface on plugin load);
4. camera autodetection runs (zero cameras found is a pass);
5. the same runtime also works when reached through a path with non-ASCII
   characters (regression check: libgphoto2 receives its plugin directories
   through the ANSI code page, and a path Python stores as UTF-8 used to
   become an unopenable directory there, so autodetection failed with
   "Error loading a library").

MSYS2 paths are removed from PATH first so a dependency accidentally resolved
from a developer's MSYS2 installation fails here instead of on a user machine.
"""

import argparse
import ctypes
import os
import shutil
import subprocess
import sys
import tempfile


def is_within(path, root):
    """Return whether ``path`` is inside the ``root`` directory."""
    path = os.path.normcase(os.path.abspath(path))
    root = os.path.normcase(os.path.abspath(root))
    return path == root or path.startswith(root + os.sep)


def strip_msys2_from_path():
    """Remove MSYS2 directories from PATH to simulate a clean machine."""
    kept = [
        entry for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry and "msys64" not in entry.lower() and "msys32" not in entry.lower()
    ]
    os.environ["PATH"] = os.pathsep.join(kept)


def ansi_non_ascii_char():
    """Return a non-ASCII character the ANSI code page can represent.

    Such a character makes a path non-ASCII for Python (which stores paths as
    UTF-8) while staying representable for ANSI-based code like the MSYS2
    libgphoto2 runtime - exactly the mix that broke plugin loading.
    """
    for byte in range(0x80, 0x100):
        try:
            char = bytes([byte]).decode("mbcs")
        except UnicodeDecodeError:
            continue
        if len(char) == 1 and not char.isascii():
            return char
    return None


def make_junction(link, target):
    """Create a directory junction, which needs no administrator rights."""
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", link, target],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def check_non_ascii_path(bundle):
    """Verify the runtime loads when reached through a non-ASCII path."""
    import LibGPhotoCamera  # already on sys.path, set up by main()

    char = ansi_non_ascii_char()
    if char is None:
        print("skipped: no non-ASCII character in this ANSI code page")
        return
    temp = tempfile.mkdtemp(prefix="gphoto2-bundle-")
    link = os.path.join(temp, "non-ascii-" + char)
    try:
        if not make_junction(link, bundle):
            print(f"skipped: could not create a junction to {bundle}")
            return
        os.environ["GPHOTO2_RUNTIME"] = link
        camera = LibGPhotoCamera.LibGPhotoCamera()
        found = camera.cameras()
        print(f"ok: runtime loads via a non-ASCII path "
              f"({len(found)} camera(s) found)")
    except Exception as error:
        sys.exit(f"FAIL: runtime did not load via a non-ASCII path: {error}")
    finally:
        os.environ["GPHOTO2_RUNTIME"] = bundle
        try:
            os.rmdir(link)  # removes the junction only, never the bundle
        except OSError:
            pass
        shutil.rmtree(temp, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        description="Verify a bundled libgphoto2 runtime loads standalone."
    )
    parser.add_argument("target", help="dist folder of the packaged app "
                        "(must contain a libgphoto2/ folder)")
    args = parser.parse_args()

    bundle = os.path.abspath(os.path.join(args.target, "libgphoto2"))
    if not os.path.isdir(os.path.join(bundle, "bin")):
        sys.exit(f"error: no bundled runtime at {bundle} - run "
                 "misc/bundle_gphoto2.py first")

    strip_msys2_from_path()
    os.environ["GPHOTO2_RUNTIME"] = bundle
    if sys.platform.startswith("win"):
        # Reproduce a frozen application's startup order: msvcrt.dll snapshots
        # the process environment when it is loaded and the MSYS2 libgphoto2
        # reads that copy. Poison CAMLIBS/IOLIBS before loading msvcrt so a
        # loader that updates only one C runtime's copy of the environment
        # (or only the OS one) fails autodetection here instead of on a user
        # machine without a configured runtime.
        os.environ["CAMLIBS"] = os.path.join(bundle, "no-such-camlibs")
        os.environ["IOLIBS"] = os.path.join(bundle, "no-such-iolibs")
        ctypes.CDLL("msvcrt.dll")
    sys.path.insert(
        0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src")
    )
    import LibGPhotoCamera

    binary_dir, camlibs, iolibs = LibGPhotoCamera._runtime_paths()
    for name, path in (("bin", binary_dir), ("camlibs", camlibs), ("iolibs", iolibs)):
        if not is_within(path, bundle):
            sys.exit(f"FAIL: {name} resolved outside the bundle: {path}")
        print(f"ok: {name} -> {path}")

    camera = LibGPhotoCamera.LibGPhotoCamera()
    for handle in (camera.gp, camera.portlib):
        if not is_within(handle._name, bundle):
            sys.exit(f"FAIL: library loaded from outside the bundle: {handle._name}")
        print(f"ok: loaded {handle._name}")

    plugins = []
    for tree in (camlibs, iolibs):
        for name in sorted(os.listdir(tree)):
            if name.lower().endswith(".dll"):
                plugins.append(os.path.join(tree, name))
    for plugin in plugins:
        try:
            ctypes.CDLL(plugin)
        except OSError as error:
            sys.exit(f"FAIL: plugin {plugin} did not load: {error}")
    print(f"ok: {len(plugins)} plugin DLLs loaded")

    found = camera.cameras()
    print(f"ok: camera autodetection ran ({len(found)} camera(s) found)")
    for entry in found:
        print(f"    {entry['model']} at {entry['port']}")

    if sys.platform.startswith("win"):
        check_non_ascii_path(bundle)
    else:
        print("skipped: non-ASCII path check is Windows-only")
    print("PASS: bundled libgphoto2 runtime is self-contained")


if __name__ == "__main__":
    main()
