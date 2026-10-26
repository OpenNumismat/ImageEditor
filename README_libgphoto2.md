# Remote capture with libgphoto2

**ImageEditor** can trigger a tethered camera and download the captured image straight to the computer using [libgphoto2](http://www.gphoto.org/proj/libgphoto2/support.php).

Captures are kept off the camera's memory card: every standard shot is taken with the capture target set to the camera's internal memory (RAM), and the downloaded file is removed from the camera afterwards.

The capture target is one of the settings you can see and choose in the camera dialog. When a camera has no internal-RAM target, **ImageEditor** refuses standard capture rather than risk writing to the card. If the camera supports preview capture, that mode is available and does not store the preview on the camera. Some cameras can use preview mode to capture a full-size image; see *The camera dialog* below.

This page describes installing and verifying `libgphoto2` and its `gphoto2` command line utility, which is also handy for testing the installation, plus the few things worth knowing about where the library keeps its settings.

## How to install libgphoto2 on Windows

Released packages bundle `libgphoto2` and all its dependencies - no library setup is needed. The bundled runtime is unpacked into a `libgphoto2` folder next to the executable; `libgphoto2/VERSIONS.txt` records the exact packaged versions, which is handy for diagnostics. Setting the `GPHOTO2_RUNTIME` environment variable forces the application to use a specific runtime instead.

The only manual step is the `WinUSB` driver for the camera (see below).

When running from source the library is not bundled and we install it with MSYS2. We will install `gphoto2` which installs the required library and enables us to test the installation. `gphoto2` is a command line utility using `libgphoto2` to work with the camera.

The library talks to a USB connected camera using a `libusb` compatible driver. For this we will install `WinUSB` driver using [Zadig](https://zadig.akeo.ie).

Note that we will install UCRT64 version (and not MINGW64).

### MSYS2 gphoto2 (running from source)

1. Download latest version of [MSYS2](https://www.msys2.org/).
2. Run the installation, keep the defaults (next, next, install, next, run now, finish).
3. Go to the terminal which opened if you left checkbox "Run now" (otherwise just open newly installed "MSYS2 UCRT64").
4. Run (and accept all):

```bash
pacman -S mingw-w64-ucrt-x86_64-gphoto2
```

### WinUSB driver (using Zadig)

1. Install [Zadig](https://zadig.akeo.ie)
2. Connect your camera (camera on).
3. Run `Zadig`, select your camera from the list and driver `WinUSB` and click install. This may take some time

### Optional checks

```bash
# print version
gphoto2 --version

# show connected camera(s)
gphoto2 --auto-detect

# basic image capture
gphoto2 --capture-image-and-download

gphoto2 --list-config
```

## Installing on Linux and macOS

No special USB driver is needed. Install `libgphoto2` and `gphoto2` from your distribution (Linux) or with [Homebrew](https://brew.sh) - `brew install libgphoto2 gphoto2` - (macOS). **ImageEditor** then loads the library from the usual library paths (on macOS it also looks in `/opt/homebrew/lib` and `/usr/local/lib`), and the checks above work the same way.

## The camera dialog

The dialog remembers the settings you choose for each camera and offers them again the next time you open it.

If you have changed settings on the camera body and want the dialog to pick up those changes, press **Use camera's current settings**. It first restores anything the dialog changed on the camera during this session, then forgets the values it remembered and reloads the camera's current settings. It is not a factory reset - `libgphoto2` reports no factory defaults - it simply shows the camera's own current settings. Two settings fall back to the dialog's first-use values instead: **Capture Size Class** (*Full Image*) and the capture target (internal memory).

Some cameras, such as the Canon EOS 350D, do not support capture to internal RAM. To get a full-size image without saving it to the card on these models, enable **Capture in preview mode** and set **Capture Size Class** to **Full Image**.

## The gphoto2 settings file (`~/.gphoto/settings`)

`libgphoto2` keeps its own preferences in a small settings file shared by every program that uses it - the `gphoto2` command line tool and **ImageEditor** alike.

On Windows it lives in your user profile:

```powershell
%USERPROFILE%\.gphoto\settings
```

It is a flat list of `section=key=value` lines, for example:

```ini
gphoto2=model=Canon EOS 40D (PTP mode)
gphoto2=port=usb:002,018
ptp2=capturetarget=sdram
libgphoto=cached-images=2
```

### Why **ImageEditor** writes to it

To keep remote capture from storing anything on the camera's memory card, **ImageEditor** takes every standard shot with the capture target set to `Internal RAM` and restores the previous target afterwards (the "Restore original capture target after each shot" option in the camera dialog, on by default).

Not every camera supports capturing to internal memory. **ImageEditor** offers standard capture only when the camera and driver provide an internal-RAM target; otherwise it refuses rather than write to the card. The dialog tries to show the relevant settings reported by `libgphoto2`, but their names and availability vary by model. If no RAM target is available, see *The camera dialog* above for a preview-capture alternative, such as the Canon EOS 350D.

Some camera models use a `capturetarget` preference stored in this file by the PTP driver. When that preference applies, its common values are:

* `ptp2=capturetarget=sdram` - `Internal RAM`
* `ptp2=capturetarget=card` - `Memory card`
* key missing - `sdram` (the `libgphoto2` default for this preference)

Whether this preference controls capture depends on the camera model and driver. Check the camera dialog for the target settings available on your camera.

The other lines are separate from capture-target selection: `gphoto2=model` and `gphoto2=port` identify the camera and port remembered by the command-line tool, while `libgphoto=cached-images` controls how many images `libgphoto2` keeps in its cache for repeated downloads.

### If the restore ever fails

If the camera is switched off or unplugged in the middle of a capture, **ImageEditor** can fail to restore the old target. On models using the PTP preference above, the key may stay at `sdram`; subsequent captures then target RAM rather than the card. To inspect or change the target, first check the choices reported for your camera:

```bash
# what it is set to now
gphoto2 --get-config capturetarget

# example values; use the exact choices reported by your camera
gphoto2 --set-config capturetarget="Memory card"
gphoto2 --set-config capturetarget="Internal RAM"
```

You can also edit the file directly and set `ptp2=capturetarget=card` (or `sdram`) by hand.
