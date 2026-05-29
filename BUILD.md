# Build Garage

## Branches de build

- `main` : branche moderne, destinee aux builds macOS recents.
- `legacy-macos` : branche dediee aux builds anciens macOS, avec dependances Python figees plus prudemment.

## Tags

- Releases modernes : `v4.4.19`
- Releases legacy macOS : `v4.4.19-legacy`

## Compatibilite macOS

Le build legacy cible Big Sur au minimum via `MACOSX_DEPLOYMENT_TARGET=11.0`.

Pour une compatibilite maximale avec Big Sur ou Catalina, un build realise directement sur le plus ancien macOS vise reste plus fiable qu'un build fait sur macOS recent avec seulement `MACOSX_DEPLOYMENT_TARGET`.

Catalina (`10.15`) peut etre tente en remplacant la cible par `10.15`, mais uniquement apres verification que Python, PyInstaller, Tk, matplotlib, numpy et Pillow restent compatibles dans cet environnement.
