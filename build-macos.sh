#!/usr/bin/env bash
set -euo pipefail

# build-macos.sh — Garage macOS (Intel x86_64) DMG
# Usage:
#   ./build-macos.sh
#   ./build-macos.sh -v 5.0.4
#   ./build-macos.sh -v 5.0.4 --flavor legacy
#   ./build-macos.sh -v 5.0.4 --keep
#
# À lancer à la racine du repo (là où il y a garage.py, assets/, data/, etc.)

VERSION="5.0.4"
KEEP_BUILD_DIRS="0"
MIN_MACOS_VERSION="${MACOSX_DEPLOYMENT_TARGET:-11.0}"
BUILD_FLAVOR="${BUILD_FLAVOR:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -v|--version) VERSION="${2:-}"; shift 2 ;;
    --flavor) BUILD_FLAVOR="${2:-}"; shift 2 ;;
    --keep) KEEP_BUILD_DIRS="1"; shift ;;
    -h|--help)
      sed -n '1,60p' "$0"
      exit 0
      ;;
    *)
      echo "Argument inconnu: $1" >&2
      exit 1
      ;;
  esac
done

# --- Pré-checks
if [[ ! -f "garage.py" ]]; then
  echo "Erreur: lance ce script depuis la racine du repo (garage.py introuvable)." >&2
  exit 1
fi

if [[ ! -d "assets" ]]; then
  echo "Erreur: dossier assets/ introuvable." >&2
  exit 1
fi

if [[ ! -d "data" ]]; then
  echo "Erreur: dossier data/ introuvable." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Erreur: python3 introuvable." >&2
  exit 1
fi

if ! python3 -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller n'est pas importable dans cet environnement."
  echo "Active ton venv puis: pip install pyinstaller" >&2
  exit 1
fi

# --- Arch (on veut x86_64 ici)
ARCH="$(uname -m)"
if [[ "$ARCH" != "x86_64" ]]; then
  echo "Attention: arch détectée = $ARCH"
  echo "Ce script va quand même nommer le DMG en x86_64 si tu ne modifies pas."
  # Tu peux choisir de bloquer ici si tu veux:
  # exit 1
fi
if [[ -n "$BUILD_FLAVOR" ]]; then
  ARCH_TAG="${BUILD_FLAVOR}-x86_64"
else
  ARCH_TAG="x86_64"
fi

# Big Sur est macOS 11.x. Déclarer cette cible évite que les binaires compilés
# pendant le build héritent par défaut de la version de macOS du poste courant.
export MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS_VERSION"
echo "==> Cible macOS minimale: ${MACOSX_DEPLOYMENT_TARGET}"

if [[ ! -f "assets/logo.png" ]]; then
  echo "Note: assets/logo.png introuvable (ce n'est pas bloquant pour le build)." >&2
fi

# --- Icone .icns
if [[ ! -f "assets/logo.icns" ]]; then
  echo "Erreur: assets/logo.icns introuvable." >&2
  exit 1
fi

# --- Dossiers sortie
mkdir -p releases

# --- Nettoyage
if [[ "$KEEP_BUILD_DIRS" == "0" ]]; then
  rm -rf build dist
fi
rm -f Garage.spec

echo "==> Build PyInstaller (Garage.app)…"
python3 -m PyInstaller \
  --clean \
  --noconfirm \
  --windowed \
  --name Garage \
  --target-arch x86_64 \
  --icon assets/logo.icns \
  --add-data "assets:assets" \
  --add-data "data:data" \
  --hidden-import=matplotlib.backends.backend_tkagg \
  --collect-submodules matplotlib.backends \
  --collect-data matplotlib \
  --collect-binaries matplotlib \
  --hidden-import=PIL._tkinter_finder \
  --hidden-import=PIL._imagingtk \
  --collect-submodules PIL \
  --collect-binaries PIL \
  garage.py

APP_PATH="dist/Garage.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Erreur: $APP_PATH introuvable après PyInstaller." >&2
  exit 1
fi

# PyInstaller expose les ressources via sys._MEIPASS. Dans les builds macOS
# récents, cet emplacement est Contents/Frameworks ; on vérifie explicitement
# la base modèle pour éviter un crash au premier lancement sur un profil neuf.
EXPECTED_DB_TEMPLATE="${APP_PATH}/Contents/Frameworks/data/garage_empty.db"
if [[ ! -f "$EXPECTED_DB_TEMPLATE" ]]; then
  FOUND_DB_TEMPLATE="$(find "$APP_PATH/Contents" -path '*/data/garage_empty.db' -type f -print -quit)"
  if [[ -n "$FOUND_DB_TEMPLATE" ]]; then
    mkdir -p "$(dirname "$EXPECTED_DB_TEMPLATE")"
    cp "$FOUND_DB_TEMPLATE" "$EXPECTED_DB_TEMPLATE"
  else
    echo "Erreur: data/garage_empty.db absent du bundle macOS." >&2
    exit 1
  fi
fi
echo "==> Base modèle embarquée: ${EXPECTED_DB_TEMPLATE#${APP_PATH}/}"

# --- Création DMG
DMG_NAME="Garage-${VERSION}-macOS-${ARCH_TAG}.dmg"
DMG_PATH="releases/${DMG_NAME}"

echo "==> Création DMG: ${DMG_PATH}"

# Répertoire temporaire "staging" pour DMG (app + lien Applications).
# Le workspace GitHub Actions offre généralement plus d'espace que le /tmp système.
DMG_WORK_DIR="$(pwd)/build/dmg"
mkdir -p "$DMG_WORK_DIR"
STAGE_DIR="$(mktemp -d "${DMG_WORK_DIR}/stage.XXXXXX")"
cleanup() {
  rm -rf "$STAGE_DIR"
  rm -f "${TMP_DMG_PATH:-}"
}
trap cleanup EXIT

cp -R "$APP_PATH" "$STAGE_DIR/"
ln -s /Applications "$STAGE_DIR/Applications"

# Volume name (ce que tu vois dans Finder quand tu montes le DMG)
VOL_NAME="Garage ${VERSION}"
TMP_DMG_PATH="${DMG_WORK_DIR}/${DMG_NAME}.tmp"

# Évite les conflits si un ancien volume Garage du même build est encore monté.
if [[ -d "/Volumes/${VOL_NAME}" ]]; then
  echo "==> Démontage ancien volume: /Volumes/${VOL_NAME}"
  hdiutil detach "/Volumes/${VOL_NAME}" -quiet || true
  sleep 2
fi

# On écrase uniquement le DMG cible exact si présent.
rm -f "$DMG_PATH"

# DMG compressé (UDZO). En CI, hdiutil peut répondre "Resource busy" de façon
# transitoire : on limite donc le retry à la création du DMG.
for attempt in 1 2 3; do
  echo "==> hdiutil create tentative ${attempt}/3"
  rm -f "$TMP_DMG_PATH"
  if hdiutil create \
    -volname "$VOL_NAME" \
    -srcfolder "$STAGE_DIR" \
    -ov \
    -format UDZO \
    "$TMP_DMG_PATH" >/dev/null; then
    mv "$TMP_DMG_PATH" "$DMG_PATH"
    break
  fi

  if [[ "$attempt" == "3" ]]; then
    echo "Erreur: création DMG impossible après 3 tentatives." >&2
    exit 1
  fi
  sleep 3
done

# --- SHA256 à côté (pratique pour release GitHub)
if command -v shasum >/dev/null 2>&1; then
  (cd releases && shasum -a 256 "$DMG_NAME" > "${DMG_NAME}.sha")
  echo "==> SHA256: releases/${DMG_NAME}.sha"
fi

echo
echo "✅ OK"
echo "DMG:   $DMG_PATH"
if [[ -f "releases/${DMG_NAME}.sha" ]]; then
  echo "SHA:   releases/${DMG_NAME}.sha"
fi
