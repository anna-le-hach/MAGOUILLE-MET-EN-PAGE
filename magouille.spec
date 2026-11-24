# -*- mode: python ; coding: utf-8 -*-
# Construire : pyinstaller magouille.spec
import sys
from PyInstaller.utils.hooks import collect_data_files

datas = [("magouille_mep/fonts", "magouille_mep/fonts"), ("magouille_mep/icone.png", "magouille_mep")] + collect_data_files("pyphen")

a = Analysis(["main.py"], datas=datas, hiddenimports=["pyphen"],
             excludes=["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia"])
pyz = PYZ(a.pure)
icon = "icone.ico" if sys.platform == "win32" else ("icone.icns" if sys.platform == "darwin" else None)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Magouille met en page", console=False, icon=icon)
    coll = COLLECT(exe, a.binaries, a.datas, name="Magouille met en page")
    app = BUNDLE(coll, name="Magouille met en page.app", icon=icon, bundle_identifier="fr.magouille.metenpage",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.1.1"})
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="Magouille met en page", console=False, icon=icon, upx=False)
