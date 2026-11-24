"""Chargement des polices (fournies + importées)."""
import os, sys, base64
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QByteArray


def resource_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, "magouille_mep") if hasattr(sys, "_MEIPASS") else base
    return d


FAMILIES = []          # familles disponibles dans les menus
_loaded_custom = {}    # clé b64[:64]+taille -> famille Qt


def load_builtin():
    d = os.path.join(resource_dir(), "fonts")
    fams = set()
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".ttf", ".otf")):
                fid = QFontDatabase.addApplicationFont(os.path.join(d, f))
                fams.update(QFontDatabase.applicationFontFamilies(fid))
    for f in ["Work Sans", "IBM Plex Sans", "EB Garamond", "Libre Baskerville", "IBM Plex Serif", "Fraunces", "Space Mono", "Bebas Neue"]:
        if f in fams and f not in FAMILIES:
            FAMILIES.append(f)
    for f in sorted(fams):
        if f not in FAMILIES:
            FAMILIES.append(f)


def register_custom(cf):
    """cf = {fam, w, it, b64}. Renvoie le nom de famille réel (ou None)."""
    key = cf["b64"][:64] + str(len(cf["b64"]))
    if key in _loaded_custom:
        return _loaded_custom[key]
    data = base64.b64decode(cf["b64"])
    fid = QFontDatabase.addApplicationFontFromData(QByteArray(data))
    if fid < 0:
        return None
    fams = QFontDatabase.applicationFontFamilies(fid)
    fam = fams[0] if fams else cf["fam"]
    _loaded_custom[key] = fam
    if fam not in FAMILIES:
        FAMILIES.append(fam)
    return fam


def all_families():
    """Polices fournies + polices du système."""
    sysf = [f for f in QFontDatabase.families() if f not in FAMILIES and not f.startswith(".")]
    return FAMILIES, sysf
