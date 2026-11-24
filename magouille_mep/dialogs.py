"""Fenêtres : accueil, format du document, export PDF, aide."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox, QDoubleSpinBox,
                               QSpinBox, QCheckBox, QDialogButtonBox, QTextBrowser, QFormLayout, QProgressBar)
from PySide6.QtCore import Qt
from .model import FORMATS
from . import APP_NAME


class Welcome(QDialog):
    def __init__(self, parent, resume_name=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME); self.choice = None
        L = QVBoxLayout(self)
        import os
        from PySide6.QtGui import QPixmap
        from . import fonts
        head = QHBoxLayout()
        ic = os.path.join(fonts.resource_dir(), "icone.png")
        if os.path.exists(ic):
            lb = QLabel(); lb.setPixmap(QPixmap(ic).scaled(72, 72, Qt.KeepAspectRatio, Qt.FastTransformation)); head.addWidget(lb)
        head.addWidget(QLabel(f"<h2 style='margin:0'>{APP_NAME}</h2>")); head.addStretch(); L.addLayout(head)
        s = QLabel("Un petit logiciel de mise en page libre et gratuit, pour fabriquer zines, livrets et affiches, et les exporter en PDF prêt à imprimer.")
        s.setWordWrap(True); s.setStyleSheet("color:#7a766e"); L.addWidget(s)
        g = QGridLayout(); g.setSpacing(10)
        cards = [("new", "Nouveau document", "Choisis le format, les marges et le nombre de pages."),
                 ("example", "Exemple : un zine A5", "Un petit livret déjà monté, pour découvrir les outils."),
                 ("open", "Ouvrir un projet", "Un fichier .json enregistré avec ce logiciel."),
                 ("help", "Comment ça marche ?", "Les bases et les raccourcis clavier.")]
        if resume_name:
            cards[3] = ("resume", f"Reprendre « {resume_name} »", "Le dernier document ouvert.")
        for k, (key, title, sub) in enumerate(cards):
            b = QPushButton(f"{title}\n{sub}"); b.setMinimumSize(300, 70)
            b.setStyleSheet("text-align:left;padding:10px;font-size:12px")
            b.clicked.connect(lambda _=0, key=key: self._pick(key))
            g.addWidget(b, k // 2, k % 2)
        L.addLayout(g)

    def _pick(self, k):
        self.choice = k; self.accept()


class SetupDialog(QDialog):
    def __init__(self, parent, d=None, is_new=True):
        super().__init__(parent)
        self.is_new = is_new
        self.setWindowTitle("Nouveau document" if is_new else "Format du document")
        d = d or {"name": "Sans titre", "w": 148, "h": 210, "bleed": 3, "facing": True, "margins": {"t": 15, "b": 20, "i": 18, "o": 14}, "cols": 1, "gutter": 5}
        L = QVBoxLayout(self); F = QFormLayout(); L.addLayout(F)
        self.name = QLineEdit(d["name"]); F.addRow("Nom", self.name)
        self.fmt = QComboBox(); self.fmt.addItems(list(FORMATS) + ["Personnalisé"])
        pre = next((k for k, (a, b) in FORMATS.items() if (a, b) in ((d["w"], d["h"]), (d["h"], d["w"]))), "Personnalisé")
        self.fmt.setCurrentText(pre); self.fmt.activated.connect(self._fmt)
        F.addRow("Format", self.fmt)
        self.W, self.H = self._sp(d["w"], 10, 2000), self._sp(d["h"], 10, 2000)
        rot = QPushButton("⟲"); rot.setToolTip("Portrait / paysage"); rot.setFixedWidth(30); rot.clicked.connect(self._rot)
        h = QHBoxLayout(); h.addWidget(self.W); h.addWidget(QLabel("×")); h.addWidget(self.H); h.addWidget(rot); F.addRow("Taille", h)
        self.pages = QSpinBox(); self.pages.setRange(1, 999); self.pages.setValue(8)
        if is_new: F.addRow("Pages", self.pages)
        self.facing = QCheckBox("Pages en vis-à-vis (livret, zine)"); self.facing.setChecked(d["facing"]); F.addRow("", self.facing)
        m = d["margins"]
        self.mt, self.mb, self.mi, self.mo = (self._sp(m[k], 0, 500) for k in "tbio")
        g = QGridLayout()
        self.li, self.lo = QLabel(), QLabel()
        for k, (lab, w) in enumerate([(QLabel("Haut"), self.mt), (QLabel("Bas"), self.mb), (self.li, self.mi), (self.lo, self.mo)]):
            g.addWidget(lab, k // 2, (k % 2) * 2); g.addWidget(w, k // 2, (k % 2) * 2 + 1)
        F.addRow("Marges", g)
        self.facing.toggled.connect(self._lab); self._lab(d["facing"])
        self.cols = QSpinBox(); self.cols.setRange(1, 12); self.cols.setValue(d["cols"])
        self.gut = self._sp(d["gutter"], 0, 100)
        h2 = QHBoxLayout(); h2.addWidget(self.cols); h2.addWidget(QLabel("gouttière")); h2.addWidget(self.gut); F.addRow("Colonnes", h2)
        self.bleed = self._sp(d["bleed"], 0, 50); F.addRow("Fonds perdus", self.bleed)
        hint = QLabel("Les fonds perdus (souvent 3 mm) sont la zone qui dépasse de la page et sera coupée au massicot : fais-y déborder les images et aplats qui touchent le bord.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#7a766e;font-size:11px"); L.addWidget(hint)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Créer" if is_new else "Appliquer"); bb.button(QDialogButtonBox.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); L.addWidget(bb)

    @staticmethod
    def _sp(v, lo, hi):
        s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(1); s.setValue(v); s.setSuffix(" mm"); return s

    def _lab(self, f):
        self.li.setText("Intérieur" if f else "Gauche"); self.lo.setText("Extérieur" if f else "Droite")

    def _fmt(self, _):
        f = FORMATS.get(self.fmt.currentText())
        if f:
            land = self.W.value() > self.H.value()
            self.W.setValue(f[1] if land else f[0]); self.H.setValue(f[0] if land else f[1])

    def _rot(self):
        a = self.W.value(); self.W.setValue(self.H.value()); self.H.setValue(a)

    def values(self):
        return dict(name=self.name.text() or "Sans titre", w=self.W.value(), h=self.H.value(), facing=self.facing.isChecked(),
                    margins={"t": self.mt.value(), "b": self.mb.value(), "i": self.mi.value(), "o": self.mo.value()},
                    cols=self.cols.value(), gutter=self.gut.value(), bleed=self.bleed.value(), pages=self.pages.value())


class ExportDialog(QDialog):
    def __init__(self, parent, d):
        super().__init__(parent)
        self.setWindowTitle("Exporter en PDF")
        n = len(d["pages"])
        L = QVBoxLayout(self); F = QFormLayout(); L.addLayout(F)
        self.allp = QComboBox(); self.allp.addItems([f"Toutes ({n})", "De… à…"]); F.addRow("Pages", self.allp)
        self.a, self.b = QSpinBox(), QSpinBox()
        for s, v in ((self.a, 1), (self.b, n)): s.setRange(1, n); s.setValue(v)
        h = QHBoxLayout(); h.addWidget(self.a); h.addWidget(QLabel("à")); h.addWidget(self.b); F.addRow("", h)
        for w in (self.a, self.b): w.setEnabled(False)
        self.allp.currentIndexChanged.connect(lambda i: [w.setEnabled(i == 1) for w in (self.a, self.b)])
        self.bleed = QCheckBox(f"Inclure les fonds perdus ({d['bleed']:g} mm)"); self.bleed.setChecked(d["bleed"] > 0); F.addRow("", self.bleed)
        self.marks = QCheckBox("Traits de coupe"); F.addRow("", self.marks)
        hint = QLabel("Pages seules, dans l’ordre de lecture. Pour imprimer un livret, passe ce PDF dans <b>Magouille s’impose</b> (sans traits de coupe). "
                      "Les couleurs CMJN du nuancier restent en CMJN, les polices sont incorporées.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#7a766e;font-size:11px"); L.addWidget(hint)
        self.bar = QProgressBar(); self.bar.hide(); L.addWidget(self.bar)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Exporter…"); bb.button(QDialogButtonBox.Cancel).setText("Annuler")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); L.addWidget(bb)

    def values(self):
        a, b = (1, self.b.maximum()) if self.allp.currentIndex() == 0 else (self.a.value(), max(self.a.value(), self.b.value()))
        return a, b, self.bleed.isChecked(), self.marks.isChecked()


HELP = """
<h2>Comment ça marche</h2>
<ol>
<li><b>Trace un bloc</b> avec l’outil Texte <code>T</code>, Image <code>F</code>, Rectangle <code>M</code> ou Ellipse <code>L</code>. Un simple clic crée un bloc à la largeur des marges.</li>
<li><b>Écris directement sur la page</b> : double-clique dans un bloc texte (ou clique dedans avec l’outil Texte). Clique pour placer le curseur, glisse pour sélectionner, double-clic pour un mot. Le style du paragraphe et le style de caractère se choisissent dans l’onglet Propriétés. Pour les longs textes, le bouton « Éditeur de texte » ouvre le texte à côté.</li>
<li><b>Fais tourner un bloc</b> avec la poignée ronde au-dessus du bloc (Maj = par 15°), ou en tapant l’angle dans Propriétés.</li>
<li><b>Fais couler le texte</b> d’un bloc à l’autre : sélectionne le bloc, clique sur le petit carré en bas à droite (rouge s’il y a du texte en excès), puis clique sur un autre bloc ou dans une page vide.</li>
<li><b>Les styles</b> (onglet Styles) règlent police, corps, interlignage, alignement… Modifie un style et tout le texte qui l’utilise suit. Les <b>styles de caractère</b> s’appliquent à quelques mots dans un paragraphe.</li>
<li><b>Les gabarits</b> (panneau de gauche) contiennent ce qui se répète : folios, titres courants. <code>{n}</code> devient le numéro de la page, <code>{t}</code> le nombre de pages.</li>
<li><b>Les images</b> : glisse-les depuis ton ordinateur, ou double-clique sur un bloc image. Surveille la résolution effective (300 ppp pour imprimer).</li>
<li><b>Contrôle</b> : l’onglet liste ce qui pose problème avant l’impression.</li>
<li><b>Exporte en PDF</b> avec fonds perdus et traits de coupe, et <b>enregistre le projet</b> (.json) pour le reprendre plus tard.</li>
</ol>
<h3>Raccourcis</h3>
<table cellpadding="3">
<tr><td><code>V T F M L</code></td><td>Sélection, Texte, Image, Rectangle, Ellipse</td></tr>
<tr><td><code>W</code></td><td>Aperçu sans repères</td></tr>
<tr><td>Ctrl+B · Ctrl+I</td><td>Gras · italique (dans le texte)</td></tr>
<tr><td>Maj+Entrée</td><td>Retour à la ligne sans nouveau paragraphe</td></tr>
<tr><td>Flèches (+ Maj)</td><td>Déplacer de 0,5 mm (5 mm)</td></tr>
<tr><td>Maj en glissant</td><td>Garder l’axe / les proportions</td></tr>
<tr><td>Alt en glissant</td><td>Sans magnétisme</td></tr>
<tr><td>Ctrl+D · Suppr</td><td>Dupliquer · Supprimer</td></tr>
<tr><td>Ctrl+Z · Ctrl+Maj+Z</td><td>Annuler · Rétablir</td></tr>
<tr><td>Ctrl+molette · + − · Ctrl+0</td><td>Zoom · Ajuster</td></tr>
<tr><td>Ctrl+S · Ctrl+E</td><td>Enregistrer · Exporter le PDF</td></tr>
<tr><td>Échap</td><td>Terminer la saisie, fermer l’éditeur, annuler le chaînage</td></tr>
</table>
<p style="color:#7a766e">Logiciel libre (licence MIT). Polices fournies sous licence SIL Open Font License.</p>
"""


class HelpDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Aide"); self.resize(560, 620)
        L = QVBoxLayout(self); t = QTextBrowser(); t.setHtml(HELP); L.addWidget(t)
        b = QPushButton("OK"); b.clicked.connect(self.accept); L.addWidget(b, 0, Qt.AlignRight)
