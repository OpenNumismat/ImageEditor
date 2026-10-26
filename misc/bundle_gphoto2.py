#!/usr/bin/env python3
"""Copy the libgphoto2 runtime from MSYS2 into a packaged application.

Packaged builds ship the runtime in a ``libgphoto2`` folder next to the
executable, laid out like an MSYS2 UCRT64 prefix so ``LibGPhotoCamera`` can use
it unchanged:

    <target>/libgphoto2/bin/*.dll
    <target>/libgphoto2/lib/libgphoto2/<version>/*.dll        (camera drivers)
    <target>/libgphoto2/lib/libgphoto2_port/<version>/*.dll   (port drivers)
    <target>/libgphoto2/VERSIONS.txt
    <target>/libgphoto2/licenses/*

Usage:
    python misc/bundle_gphoto2.py <target-dist-dir>
        [--msys2-root C:\\msys64\\ucrt64] [--skip lumix]

The DLL dependency closure is computed with ldd at build time; a known-good
fallback list is used when ldd is unavailable. Nothing is downloaded: the
runtime comes from the MSYS2 installation (``pacman -S
mingw-w64-ucrt-x86_64-libgphoto2``).
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

# DLLs exported by the runtime itself; everything else (libexif, libintl,
# libltdl, libusb, ...) is found through the dependency closure.
CORE_DLL_PATTERNS = ("libgphoto2-*.dll", "libgphoto2_port-*.dll")

# Plugin trees copied under lib/, preserving the <version> subdirectory.
PLUGIN_TREES = (
    os.path.join("lib", "libgphoto2"),
    os.path.join("lib", "libgphoto2_port"),
)

# Used only when ldd cannot be run: runtime dependencies of libgphoto2 and its
# plugins (camlib/iolib) on top of the Windows system DLLs.
FALLBACK_DEPENDENCIES = (
    "libexif-12.dll",
    "libiconv-2.dll",
    "libintl-8.dll",
    "libjpeg-8.dll",
    "libltdl-7.dll",
    "libsystre-0.dll",
    "libtre-5.dll",
    "libusb-1.0.dll",
    "libwinpthread-1.dll",
    "libxml2-16.dll",
    "zlib1.dll",
)


def msys2_home(msys2_root):
    """Return the MSYS2 home directory for a UCRT64-style prefix."""
    return os.path.dirname(os.path.normpath(msys2_root))


def run_bash(msys2_root, command):
    """Run a command in the MSYS2 login shell, returning its stdout."""
    bash = os.path.join(msys2_home(msys2_root), "usr", "bin", "bash.exe")
    result = subprocess.run(
        [bash, "-lc", command], capture_output=True, text=True, check=False
    )
    return result


def find_dlls(msys2_root):
    """Return the core libgphoto2 DLLs from the MSYS2 prefix."""
    binary_dir = os.path.join(msys2_root, "bin")
    dlls = []
    for pattern in CORE_DLL_PATTERNS:
        found = sorted(glob.glob(os.path.join(binary_dir, pattern)))
        if not found:
            sys.exit(f"error: no {pattern} in {binary_dir} - install "
                     "mingw-w64-ucrt-x86_64-libgphoto2 first")
        dlls.extend(found)
    return dlls


def find_plugins(msys2_root, skip):
    """Return {plugin tree: [plugin DLLs]} from the MSYS2 prefix."""
    plugins = {}
    for tree in PLUGIN_TREES:
        base = os.path.join(msys2_root, tree)
        versions = sorted(
            name for name in os.listdir(base)
            if os.path.isdir(os.path.join(base, name))
            and all(part.isdigit() for part in name.split("."))
        )
        if not versions:
            sys.exit(f"error: no versioned plugin directory in {base}")
        version = versions[-1]
        dlls = [
            path for path in sorted(glob.glob(os.path.join(base, version, "*.dll")))
            if os.path.splitext(path)[0].split(os.sep)[-1] not in skip
        ]
        plugins[os.path.join(tree, version)] = dlls
    return plugins


def to_posix(msys2_root, paths):
    """Convert Windows paths to their MSYS2 POSIX form."""
    return _convert_paths(msys2_root, paths, "-u")


def to_windows(msys2_root, paths):
    """Convert MSYS2 POSIX paths to their Windows form."""
    return _convert_paths(msys2_root, paths, "-w")


def _convert_paths(msys2_root, paths, flag):
    command = "cygpath " + flag + " " + " ".join(f'"{path}"' for path in paths)
    result = run_bash(msys2_root, command)
    if result.returncode != 0:
        sys.exit(f"error: cygpath failed: {result.stderr.strip()}")
    return result.stdout.split()


def ldd_scan(msys2_root, dll):
    """Return (dependencies, unresolved imports) of one DLL.

    The runtime bin directory is put on PATH first: ldd resolves through the
    Windows DLL search order, so dependencies of the plugin DLLs (which live
    outside bin/) are otherwise reported as "not found" even though they ship
    with the runtime. API-set imports (api-ms-win-*) are ignored: Windows
    resolves them from the OS.
    """
    binary_dir = os.path.join(msys2_root, "bin")
    posix_bin = to_posix(msys2_root, [binary_dir])[0]
    result = run_bash(
        msys2_root,
        f'export PATH="{posix_bin}:$PATH"; ldd "{dll}"',
    )
    if result.returncode != 0:
        sys.exit(f"error: ldd failed for {dll}: {result.stderr.strip()}")
    dependencies, unresolved = [], []
    posix_paths = []
    for line in result.stdout.splitlines():
        if " => " not in line:
            continue
        name, rest = line.split(" => ", 1)
        if rest.startswith("not found"):
            if not name.strip().lower().startswith("api-ms-win-"):
                unresolved.append(name.strip())
        else:
            posix_paths.append(rest.rsplit(" (0x", 1)[0].strip())
    if posix_paths:
        dependencies = to_windows(msys2_root, posix_paths)
    return dependencies, unresolved


def dependency_closure(msys2_root, seeds):
    """Return the transitive MSYS2 DLL dependencies of ``seeds`` (ldd-based)."""
    closure = set()
    unresolved = set()
    pending = list(seeds)
    while pending:
        dll = pending.pop()
        dependencies, missing = ldd_scan(msys2_root, dll)
        unresolved.update(missing)
        for dependency in dependencies:
            dependency = os.path.normcase(os.path.abspath(dependency))
            if os.path.dirname(dependency) == os.path.normcase(os.path.join(msys2_root, "bin")) \
                    and dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    if unresolved:
        sys.exit("error: unresolved DLL dependencies: "
                 + ", ".join(sorted(unresolved)))
    return sorted(closure)


def fallback_dependencies(msys2_root):
    """Return the hardcoded dependency list resolved against the prefix."""
    binary_dir = os.path.join(msys2_root, "bin")
    return [
        path for path in (
            os.path.join(binary_dir, name) for name in FALLBACK_DEPENDENCIES
        )
        if os.path.isfile(path)
    ]


def owning_packages(msys2_root, sources):
    """Return {package: version} owning the given MSYS2 source files."""
    command = "pacman -Qo " + " ".join(f'"{path}"' for path in to_posix(msys2_root, sources))
    result = run_bash(msys2_root, command)
    if result.returncode != 0:
        return {}
    owned = {}
    for line in result.stdout.splitlines():
        match = re.search(r"is owned by (\S+) (\S+)", line)
        if match:
            owned[match.group(1)] = match.group(2)
    return owned


def write_versions(msys2_root, sources):
    """Return a VERSIONS.txt body recording owning packages of the bundle."""
    lines = ["# libgphoto2 runtime bundled at build time", ""]
    owned = owning_packages(msys2_root, sources)
    if owned:
        for package, version in sorted(owned.items()):
            lines.append(f"{package} {version}")
    else:
        lines.append("# pacman -Qo unavailable; package versions not recorded")
    return "\n".join(lines) + "\n"


def copy_licenses(msys2_root, target, sources):
    """Copy license directories of the owning packages into the bundle."""
    license_target = os.path.join(target, "licenses")
    copied_count = 0
    share_licenses = os.path.join(msys2_root, "share", "licenses")
    for package in owning_packages(msys2_root, sources):
        # MSYS2 license directories are named after the package name without
        # the mingw-w64-ucrt-x86_64- prefix; accept both spellings.
        short_name = package.split("x86_64-")[-1]
        for name in (short_name, package):
            source = os.path.join(share_licenses, name)
            if os.path.isdir(source):
                shutil.copytree(
                    source, os.path.join(license_target, name),
                    dirs_exist_ok=True,
                )
                copied_count += 1
                break
    return copied_count


def main():
    parser = argparse.ArgumentParser(
        description="Bundle the MSYS2 libgphoto2 runtime into a packaged app."
    )
    parser.add_argument("target", help="dist folder of the packaged app "
                        "(a libgphoto2/ folder is created inside it)")
    parser.add_argument("--msys2-root",
                        default=os.environ.get("MSYS2_ROOT", r"C:\msys64\ucrt64"),
                        help="MSYS2 UCRT64 prefix (default: %%MSYS2_ROOT%% or "
                             "C:\\msys64\\ucrt64)")
    parser.add_argument("--skip", action="append", default=[],
                        metavar="PLUGIN",
                        help="camlib/iolib plugin name to exclude (e.g. lumix)")
    args = parser.parse_args()

    msys2_root = os.path.abspath(args.msys2_root)
    if not os.path.isdir(os.path.join(msys2_root, "bin")):
        sys.exit(f"error: no MSYS2 prefix at {msys2_root}")
    if not os.path.isdir(args.target):
        sys.exit(f"error: no target directory {args.target}")

    skip = {os.path.splitext(name)[0] for name in args.skip}
    bundle = os.path.join(args.target, "libgphoto2")
    binary_target = os.path.join(bundle, "bin")

    core_dlls = find_dlls(msys2_root)
    plugins = find_plugins(msys2_root, skip)

    print(f"Bundling libgphoto2 runtime from {msys2_root} into {bundle}")
    seeds = core_dlls + [dll for dlls in plugins.values() for dll in dlls]
    try:
        dependencies = dependency_closure(msys2_root, seeds)
        print(f"ldd dependency closure: {len(dependencies)} DLLs")
    except OSError as error:
        print(f"warning: ldd unavailable ({error}); using fallback list")
        dependencies = fallback_dependencies(msys2_root)

    os.makedirs(binary_target, exist_ok=True)
    copied = []
    sources = []
    for dll in core_dlls + dependencies:
        destination = os.path.join(binary_target, os.path.basename(dll))
        shutil.copy2(dll, destination)
        copied.append(destination)
        sources.append(dll)

    for tree, dlls in plugins.items():
        plugin_target = os.path.join(bundle, tree)
        os.makedirs(plugin_target, exist_ok=True)
        for dll in dlls:
            destination = os.path.join(plugin_target, os.path.basename(dll))
            shutil.copy2(dll, destination)
            copied.append(destination)
            sources.append(dll)
        print(f"  {tree}: {len(dlls)} plugins")

    with open(os.path.join(bundle, "VERSIONS.txt"), "w", encoding="utf-8") as handle:
        handle.write(write_versions(msys2_root, sources))
    license_count = copy_licenses(msys2_root, bundle, sources)

    total_size = sum(os.path.getsize(path) for path in copied)
    print(f"Copied {len(copied)} files ({total_size // 1024 // 1024} MB), "
          f"{license_count} license directories")
    print(f"Done: {bundle}")


if __name__ == "__main__":
    main()
