# Build Garage

## Build profiles

Garage keeps one code branch. Compatibility differences are handled by build profiles.

- `macos-modern`: GitHub Actions macOS Intel runner with Python 3.12 and current build dependencies.
- `macos-legacy`: local or self-hosted build on an older Intel Mac with Python 3.11, `MACOSX_DEPLOYMENT_TARGET=11.0`, and pinned legacy build dependencies.
- `linux`: Ubuntu build for AppImage and tar.gz.
- `windows`: Windows build for portable zip.

## macOS compatibility

The legacy macOS profile targets Big Sur or newer with `MACOSX_DEPLOYMENT_TARGET=11.0`.

Catalina (`10.15`) may be tested by lowering `MACOSX_DEPLOYMENT_TARGET`, but the result also depends on Python, Tk, PyInstaller, matplotlib, numpy, and Pillow compatibility.

For maximum compatibility with an older macOS release, build on the oldest macOS version you want to support.

GitHub-hosted `macos-13` runners are not reliable enough for the legacy profile. Use GitHub Actions for the current release artifacts, and build legacy macOS manually on a controlled machine:

```bash
python3 -m pip install -r requirements-build-macos-legacy.txt
MACOSX_DEPLOYMENT_TARGET=11.0 ./build-macos.sh -v 4.4.22 --flavor legacy
```
