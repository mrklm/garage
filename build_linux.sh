cat > build_linux.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------
# Build Linux Garage (AppImage + tar.gz)
# Sortie dans ./releases/
#
# Usage:
#   ./build_linux.sh              -> version par défaut
#   ./build_linux.sh 4.4.6        -> version passée en argument
# ----------------------------------------------------

APP_NAME="Garage"
DEFAULT_VERSION="4.4.5"
VERSION="${1:-$DEFAULT_VERSION}"
ARCH="$(uname -m)"   # ex: x86_64, aarch64

ROOT_DIR="$(pwd)"
DIST_DIR="${ROOT_DIR}/dist"
BUILD_DIR="${ROOT_DIR}/build"
APPDIR="${ROOT_DIR}/AppDir"
APPIMAGE_TOOL="${ROOT_DIR}/appimagetool.AppImage"
RELEASES_DIR="${ROOT_DIR}/releases"

APPIMAGE_OUT="${APP_NAME}-linux-${ARCH}-v${VERSION}.AppImage"
TAR_DIR="${APP_NAME}-${VERSION}-linux-${ARCH}"
TAR_OUT="${TAR_DIR}.tar.gz"
SHA_OUT="SHA256SUMS-${APP_NAME}-v${VERSION}.txt"

# ---- helpers -------------------------------------------------
die() { echo "❌ $*" >&2; exit 1; }
info() { echo "➡️  $*"; }
ok() { echo "✅ $*"; }

# ---- sanity checks ------------------------------------------
[[ -f "${ROOT_DIR}/garage.py" ]] || die "garage.py introuvable. Lance le script à la racine du repo."
[[ -d "${ROOT_DIR}/assets" ]] || die "Dossier assets introuvable."
[[ -d "${ROOT_DIR}/data" ]] || die "Dossier data introuvable."

command -v python3 >/dev/null 2>&1 || die "python3 introuvable."
command -v wget   >/dev/null 2>&1 || die "wget introuvable (sudo apt install wget)."

mkdir -p "${RELEASES_DIR}"

# ---- venv ---------------------------------------------------
info "Création / activation du venv .venv"
if [[ ! -d "${ROOT_DIR}/.venv" ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source "${ROOT_DIR}/.venv/bin/activate"

info "Python utilisé : $(which python)"
info "Version Python : $(python --version)"
info "Target ARCH    : ${ARCH}"
info "Version build  : ${VERSION}"

# ---- pip deps -----------------------------------------------
info "Mise à jour pip / setuptools / wheel"
python -m ensurepip --upgrade >/dev/null 2>&1 || true
python -m pip install --upgrade pip setuptools wheel

if [[ -f "${ROOT_DIR}/requirements-build.txt" ]]; then
  info "Installation deps via requirements-build.txt"
  pip install -r requirements-build.txt
else
  info "requirements-build.txt absent → deps par défaut"
  pip install pyinstaller pillow matplotlib
fi

# ---- clean old artifacts ------------------------------------
info "Nettoyage anciens artefacts (build/, dist/, *.spec)"
rm -rf "${BUILD_DIR}" "${DIST_DIR}" ./*.spec

# ---- PyInstaller build --------------------------------------
info "Build PyInstaller (--onefile)"
pyinstaller --noconfirm --clean \
  --name "${APP_NAME}" \
  --onefile \
  --windowed \
  --add-data "assets:assets" \
  --add-data "data:data" \
  --hidden-import=matplotlib.backends.backend_tkagg \
  --hidden-import=PIL._tkinter_finder \
  --hidden-import=PIL._imagingtk \
  --collect-submodules PIL \
  --collect-binaries PIL \
  garage.py

[[ -x "${DIST_DIR}/${APP_NAME}" ]] || die "Binaire dist/${APP_NAME} introuvable."

# ---- smoke test ---------------------------------------------
info "Test rapide du binaire PyInstaller"
set +e
"${DIST_DIR}/${APP_NAME}" >/dev/null 2>&1 &
PID=$!
sleep 1
kill "$PID" >/dev/null 2>&1 || true
wait "$PID" >/dev/null 2>&1 || true
set -e
ok "Le binaire se lance (test smoke OK)."

# ---- AppDir -------------------------------------------------
info "Préparation AppDir"
rm -rf "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"

cp "${DIST_DIR}/${APP_NAME}" "${APPDIR}/usr/bin/${APP_NAME}"
chmod +x "${APPDIR}/usr/bin/${APP_NAME}"

# ---- icon (logo.png, casse respectée) -----------------------
if [[ -f "${ROOT_DIR}/assets/logo.png" ]]; then
  cp "${ROOT_DIR}/assets/logo.png" "${APPDIR}/${APP_NAME}.png"
else
  die "Icône assets/logo.png introuvable (attention à la casse)."
fi

# ---- Desktop file (AppImage) --------------------------------
cat > "${APPDIR}/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=${APP_NAME}
Icon=${APP_NAME}
Categories=Utility;
Terminal=false
EOF

# ---- AppRun -------------------------------------------------
cat > "${APPDIR}/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/Garage" "$@"
EOF
chmod +x "${APPDIR}/AppRun"

# ---- appimagetool -------------------------------------------
if [[ ! -f "${APPIMAGE_TOOL}" ]]; then
  info "Téléchargement appimagetool"
  wget -O "${APPIMAGE_TOOL}" \
    https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
  chmod +x "${APPIMAGE_TOOL}"
else
  chmod +x "${APPIMAGE_TOOL}" || true
fi

# ---- Build AppImage -----------------------------------------
info "Création AppImage : ${RELEASES_DIR}/${APPIMAGE_OUT}"
"${APPIMAGE_TOOL}" "${APPDIR}" "${RELEASES_DIR}/${APPIMAGE_OUT}"
[[ -f "${RELEASES_DIR}/${APPIMAGE_OUT}" ]] || die "AppImage non créée."
ok "AppImage créée : ${RELEASES_DIR}/${APPIMAGE_OUT}"

# ---- Build tar.gz -------------------------------------------
info "Création tar.gz : ${RELEASES_DIR}/${TAR_OUT}"
rm -rf "${ROOT_DIR:?}/${TAR_DIR}"
mkdir -p "${ROOT_DIR}/${TAR_DIR}"
cp "${DIST_DIR}/${APP_NAME}" "${ROOT_DIR}/${TAR_DIR}/${APP_NAME}"
chmod +x "${ROOT_DIR}/${TAR_DIR}/${APP_NAME}"

tar czvf "${RELEASES_DIR}/${TAR_OUT}" "${TAR_DIR}" >/dev/null
[[ -f "${RELEASES_DIR}/${TAR_OUT}" ]] || die "tar.gz non créée."
ok "tar.gz créé : ${RELEASES_DIR}/${TAR_OUT}"

# ---- checksums ----------------------------------------------
info "SHA256 (optionnel)"
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum "${RELEASES_DIR}/${APPIMAGE_OUT}" "${RELEASES_DIR}/${TAR_OUT}" \
    | tee "${RELEASES_DIR}/${SHA_OUT}" >/dev/null
  ok "SHA256SUMS généré : ${RELEASES_DIR}/${SHA_OUT}"
else
  info "sha256sum absent → skip"
fi

ok "FINI ✅"
echo
echo "Fichiers prêts à publier :"
echo " - ${RELEASES_DIR}/${APPIMAGE_OUT}"
echo " - ${RELEASES_DIR}/${TAR_OUT}"
echo " - ${RELEASES_DIR}/${SHA_OUT} (si généré)"
echo
echo "Astuce git : ajoute 'releases/' à .gitignore (artefacts de release)."
SH

chmod +x build_linux.sh
