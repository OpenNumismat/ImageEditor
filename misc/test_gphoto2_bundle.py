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
4. camera autodetection runs (zero cameras found is a pass).

MSYS2 paths are removed from PATH first so a dependency accidentally resolved
from a developer's MSYS2 installation fails here instead of on a user machine.
"""

import argparse
import ctypes
import os
import sys


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
    print("PASS: bundled libgphoto2 runtime is self-contained")


if __name__ == "__main__":
    main()
