#!/bin/bash
# Construit "Magouille met en page.app" dans le dossier dist
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller magouille.spec --noconfirm
echo "C'est prêt : dist/Magouille met en page.app"
