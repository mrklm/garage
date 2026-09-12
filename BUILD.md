# Build Garage

## Build profiles

Garage keeps one code branch. Compatibility differences are handled by build profiles.

- `macos-modern`: GitHub Actions macOS Intel runner with Python 3.12 and current build dependencies.
- `macos-legacy`: local or self-hosted build on an older Intel Mac with Python 3.11, `MACOSX_DEPLOYMENT_TARGET=11.0`, and pinned legacy build dependencies.
- `linux`: Ubuntu build for AppImage and tar.gz.
- `windows`: Windows build for portable zip.

## Standard release

The standard release is produced by the GitHub Actions workflow when a version tag is pushed:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The workflow builds the modern macOS, Linux, and Windows artifacts, then publishes a single GitHub Release with the final artifacts and their checksum files attached directly.

High Sierra builds are not part of the standard release workflow.

## macOS compatibility

The legacy macOS profile targets Big Sur or newer with `MACOSX_DEPLOYMENT_TARGET=11.0`.

Catalina (`10.15`) may be tested by lowering `MACOSX_DEPLOYMENT_TARGET`, but the result also depends on Python, Tk, PyInstaller, matplotlib, numpy, and Pillow compatibility.

For maximum compatibility with an older macOS release, build on the oldest macOS version you want to support.

GitHub-hosted `macos-13` runners are not reliable enough for the legacy profile. Use GitHub Actions for the current release artifacts, and build legacy macOS manually on a controlled machine:

```bash
python3 -m pip install -r requirements-build-macos-legacy.txt
MACOSX_DEPLOYMENT_TARGET=11.0 ./build-macos.sh -v 4.5.29 --flavor legacy
```

High Sierra compatibility must be built and published separately from the standard macOS/Linux/Windows release, with a clearly distinct artifact name such as `high-sierra` or `legacy`.
