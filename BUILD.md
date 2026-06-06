# Build Garage

## Build profiles

Garage keeps one code branch. Compatibility differences are handled by build profiles.

- `macos-modern`: recent macOS runner and current build dependencies.
- `macos-legacy`: macOS 13 runner, Python 3.11, `MACOSX_DEPLOYMENT_TARGET=11.0`, and pinned legacy build dependencies.
- `linux`: Ubuntu build for AppImage and tar.gz.
- `windows`: Windows build for portable zip.

## macOS compatibility

The legacy macOS profile targets Big Sur or newer with `MACOSX_DEPLOYMENT_TARGET=11.0`.

Catalina (`10.15`) may be tested by lowering `MACOSX_DEPLOYMENT_TARGET`, but the result also depends on Python, Tk, PyInstaller, matplotlib, numpy, and Pillow compatibility.

For maximum compatibility with an older macOS release, build on the oldest macOS version you want to support.
