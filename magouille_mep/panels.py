"""Panneaux : pages, propriétés, styles, nuancier, contrôle."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox, QDoubleSpinBox,
                               QSpinBox, QLineEdit, QCheckBox, QListWidget, QListWidgetItem, QSlider, QButtonGroup, QScrollArea,
                               QFrame, QColorDialog, QSizePolicy)
from PySide6.QtGui import QColor, QPixmap, QIcon, QFont, QPainter
from PySide6.QtCore import Qt, Signal, QSize
from . import fonts
from .textflow import swatch_qcolor
from .render import item_bounds

MUTED = "color:#7a766e"


def spin(v, lo=-9999, hi=9999, step=0.5, dec=2, suffix=" mm"):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setSingleStep(step); s.setValue(v)
    s.setSuffix(suffix); s.setKeyboardTracking(False); return s


def h3(t):
    l = QLabel(t.upper()); l.setStyleSheet("color:#7a766e;font-size:10px;font-weight:600;letter-spacing:1px;margin-top:8px"); return l


def hint(t):
    l = QLabel(t); l.setWordWrap(True); l.setStyleSheet(MUTED + ";font-size:11px"); l.setTextFormat(Qt.RichText); return l


def clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        wd = it.widget()
        if wd: wd.hide(); wd.setParent(None); wd.deleteLater()
        elif it.layout(): clear(it.layout())


def row(*ws):
    h = QHBoxLayout(); h.setSpacing(4)
    for w in ws:
        if w == "stretch": h.addStretch()
        else: h.addWidget(w)
    return h


def chip(col):
    pm = QPixmap(16, 16); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setPen(QColor(150, 150, 150))
    if col is None:
        p.fillRect(0, 0, 15, 15, Qt.white); p.setPen(QColor(220, 50, 50)); p.drawLine(1, 14, 14, 1); p.setPen(QColor(150, 150, 150))
    else:
        p.fillRect(0, 0, 15, 15, col)
    p.drawRect(0, 0, 15, 15); p.end()
    return QIcon(pm)


def swatch_combo(doc, cur, none=True):
    c = QComboBox()
    if none: c.addItem(chip(None), "Aucune", None)
    for s in doc.d["swatches"]:
        c.addItem(chip(swatch_qcolor(doc, s["id"])), s["name"], s["id"])
    i = c.findData(cur)
    c.setCurrentIndex(max(0, i))
    return c


class Scroll(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True); self.setFrameShape(QFrame.NoFrame)
        self.inner = QWidget(); self.lay = QVBoxLayout(self.inner); self.lay.setAlignment(Qt.AlignTop)
        self.setWidget(self.inner)


# ---------------------------------------------------------------- Pages
class PagesPanel(QWidget):
    def __init__(self, win):
        super().__init__(); self.win = win
        lay = QVBoxLayout(self); lay.setContentsMargins(8, 4, 8, 8)
        hm = QHBoxLayout(); hm.addWidget(h3("Gabarits")); hm.addStretch()
        b = QPushButton("+"); b.setFixedWidth(26); b.setToolTip("Nouveau gabarit"); b.clicked.connect(win.add_master); hm.addWidget(b)
        lay.addLayout(hm)
        self.masters = QListWidget(); self.masters.setMaximumHeight(90); self.masters.itemClicked.connect(lambda it: win.enter_master(it.data(Qt.UserRole)))
        lay.addWidget(self.masters)
        hp = QHBoxLayout(); hp.addWidget(h3("Pages")); hp.addStretch()
        b = QPushButton("+"); b.setFixedWidth(26); b.setToolTip("Ajouter une page à la fin"); b.clicked.connect(lambda: win.page_op("add")); hp.addWidget(b)
        lay.addLayout(hp)
        self.pages = QListWidget(); self.pages.setViewMode(QListWidget.IconMode); self.pages.setIconSize(QSize(34, 46))
        self.pages.setMovement(QListWidget.Static); self.pages.setResizeMode(QListWidget.Adjust); self.pages.setSpacing(4)
        self.pages.itemClicked.connect(lambda it: win.goto_page(it.data(Qt.UserRole)))
        lay.addWidget(self.pages, 1)
        self.props = QVBoxLayout(); lay.addLayout(self.props)

    def refresh(self):
        win, d = self.win, self.win.doc.d
        self.masters.clear()
        for m in d["masters"]:
            it = QListWidgetItem(f"{m['id']}  {m['name']}"); it.setData(Qt.UserRole, m["id"]); self.masters.addItem(it)
            if win.renderer.mode == "master" and win.renderer.master == m["id"]: it.setSelected(True)
        self.pages.clear()
        for i, p in enumerate(d["pages"]):
            pm = QPixmap(34, 46); pm.fill(Qt.white); qp = QPainter(pm); qp.setPen(QColor(170, 170, 170)); qp.drawRect(0, 0, 33, 45)
            qp.setPen(QColor(150, 150, 150)); f = qp.font(); f.setPointSize(7); qp.setFont(f); qp.drawText(3, 11, p.get("m") or ""); qp.end()
            it = QListWidgetItem(QIcon(pm), str(i + 1)); it.setData(Qt.UserRole, p["id"]); self.pages.addItem(it)
            if win.renderer.mode == "pages" and p["id"] == win.cur_page: it.setSelected(True)
        clear(self.props)
        if win.renderer.mode == "master":
            m = next(m for m in d["masters"] if m["id"] == win.renderer.master)
            self.props.addWidget(h3(f"Gabarit {m['id']}"))
            name = QLineEdit(m["name"]); name.editingFinished.connect(lambda: win.rename_master(name.text()))
            self.props.addLayout(row(QLabel("Nom"), name))
            bd = QPushButton("Supprimer"); bd.setEnabled(len(d["masters"]) > 1); bd.clicked.connect(win.del_master)
            bx = QPushButton("Retour aux pages"); bx.clicked.connect(win.exit_master)
            self.props.addLayout(row(bd, bx))
            self.props.addWidget(hint("Ce que tu poses ici apparaît sur toutes les pages qui utilisent ce gabarit. Le texte <b>{n}</b> devient le numéro de page."))
            return
        idx = next((i for i, p in enumerate(d["pages"]) if p["id"] == win.cur_page), None)
        if idx is None: return
        pg = d["pages"][idx]
        self.props.addWidget(h3(f"Page {idx + 1}"))
        cb = QComboBox(); cb.addItem("Aucun", "")
        for m in d["masters"]: cb.addItem(m["name"], m["id"])
        cb.setCurrentIndex(max(0, cb.findData(pg.get("m") or "")))
        cb.activated.connect(lambda _: win.set_page_master(cb.currentData()))
        self.props.addLayout(row(QLabel("Gabarit"), cb))
        b1, b2, b3, b4 = QPushButton("+ Après"), QPushButton("↑"), QPushButton("↓"), QPushButton("Supprimer")
        b1.setToolTip("Insérer une page après celle-ci")
        b1.clicked.connect(lambda: win.page_op("ins")); b2.clicked.connect(lambda: win.page_op("up")); b3.clicked.connect(lambda: win.page_op("down")); b4.clicked.connect(lambda: win.page_op("del"))
        b2.setEnabled(idx > 0); b3.setEnabled(idx < len(d["pages"]) - 1); b4.setEnabled(len(d["pages"]) > 1)
        for b in (b2, b3): b.setFixedWidth(30)
        self.props.addLayout(row(b1, b2, b3, b4))
        n = len(d["pages"])
        self.props.addWidget(hint(f"{n} pages" + (" · pour une piqûre à cheval, vise un multiple de 4" if d["facing"] and n % 4 else "")))


# ---------------------------------------------------------------- Propriétés
class PropsPanel(Scroll):
    def __init__(self, win):
        super().__init__(); self.win = win; self.geo = {}; self.tt = None

    def text_tools(self, L):
        win, D = self.win, self.win.doc
        L.addWidget(QLabel("<b>Saisie du texte sur la page</b>"))
        ps = QComboBox()
        for s in D.d["styles"]: ps.addItem(s["name"], s["id"])
        ps.activated.connect(lambda _: (win.page_text.set_para_style(ps.currentData()), win.canvas.setFocus()) if win.page_text else None)
        cs = QComboBox(); cs.addItem("Aucun", "")
        for c in D.d.get("charStyles", []): cs.addItem(c["name"], c["id"])
        cs.activated.connect(lambda _: (win.page_text.set_char_style(cs.currentData()), win.canvas.setFocus()) if win.page_text else None)
        lb1, lb2 = QLabel("Paragraphe"), QLabel("Caractère")
        L.addLayout(row(lb1, ps)); L.addLayout(row(lb2, cs))
        bb, bi = QPushButton("G"), QPushButton("I")
        f = bb.font(); f.setBold(True); bb.setFont(f); f = bi.font(); f.setItalic(True); bi.setFont(f)
        for b in (bb, bi): b.setFixedWidth(34); b.setFocusPolicy(Qt.NoFocus)
        bb.clicked.connect(lambda: (win.page_text.toggle(0), win.canvas.update()) if win.page_text else None)
        bi.clicked.connect(lambda: (win.page_text.toggle(1), win.canvas.update()) if win.page_text else None)
        bf = QPushButton("N° page"); bf.setFocusPolicy(Qt.NoFocus); bf.setToolTip("Insérer le numéro de page")
        bf.clicked.connect(lambda: win.page_text.insert("{n}") if win.page_text else None)
        bl = QPushButton("Faux texte"); bl.setFocusPolicy(Qt.NoFocus)
        from .model import FAUX_TEXTE
        bl.clicked.connect(lambda: win.page_text.insert("\n".join(FAUX_TEXTE)) if win.page_text else None)
        L.addLayout(row(bb, bi, bf, bl, "stretch"))
        be = QPushButton("Éditeur de texte"); be.setToolTip("Ouvrir le texte dans l'éditeur à côté (pratique pour les longs textes)")
        be.clicked.connect(lambda: win.open_editor(win.page_text.sid) if win.page_text else None)
        bt = QPushButton("Terminer (Échap)"); bt.clicked.connect(win.end_page_text)
        L.addLayout(row(be, bt))
        L.addWidget(hint("Clique dans le texte pour placer le curseur, glisse pour sélectionner, double-clic pour un mot. "
                         "Ctrl+B / Ctrl+I : gras / italique. Maj+Entrée : retour à la ligne sans changer de paragraphe."))
        self.tt = (ps, cs)
        self.sync_text_tools()

    def sync_text_tools(self):
        pt = self.win.page_text
        if not pt or not self.tt: return
        ps, cs = self.tt
        try:
            for c, v in ((ps, pt.current_para_style()), (cs, pt.current_char_style())):
                c.blockSignals(True); c.setCurrentIndex(max(0, c.findData(v))); c.blockSignals(False)
        except RuntimeError:
            self.tt = None

    def refresh(self):
        win, D = self.win, self.win.doc
        clear(self.lay); self.geo = {}; self.tt = None
        L = self.lay
        if win.page_text:
            self.text_tools(L); L.addWidget(h3(""))
        sel = [D.item(i) for i in win.sel if D.item(i)]
        if not sel:
            d = D.d
            L.addWidget(QLabel(f"<b>{d['name']}</b>"))
            L.addWidget(hint(f"{d['w']:g} × {d['h']:g} mm · {len(d['pages'])} pages{' en vis-à-vis' if d['facing'] else ''} · fonds perdus {d['bleed']:g} mm"))
            b = QPushButton("Format du document…"); b.clicked.connect(win.setup_dialog); L.addWidget(b)
            L.addWidget(hint("Choisis un outil à gauche et trace un bloc sur une page. Double-clique sur un bloc texte pour écrire dedans, sur un bloc image pour choisir une image. Tu peux aussi glisser une image depuis ton ordinateur."))
            return
        if len(sel) > 1:
            L.addWidget(QLabel(f"<b>{len(sel)} blocs sélectionnés</b>")); L.addWidget(hint("Aligner"))
            g = QGridLayout()
            for k, (key, name) in enumerate([("l", "Gauche"), ("c", "Centre"), ("r", "Droite"), ("t", "Haut"), ("m", "Milieu"), ("b", "Bas")]):
                b = QPushButton(name); b.clicked.connect(lambda _=0, key=key: win.align_sel(key)); g.addWidget(b, k // 3, k % 3)
            L.addLayout(g); self._arrange(L); return
        it = sel[0]
        L.addWidget(QLabel("<b>" + {"text": "Bloc texte", "image": "Bloc image", "rect": "Rectangle", "ellipse": "Ellipse"}[it["type"]] + (" (gabarit)" if "m" in it["on"] else "") + "</b>"))
        g = QGridLayout()
        for k, (key, lab) in enumerate([("x", "X"), ("y", "Y"), ("w", "L"), ("h", "H")]):
            s = spin(it[key], 1 if key in "wh" else -9999); self.geo[key] = s
            s.valueChanged.connect(lambda v, key=key: win.set_prop(key, v))
            g.addWidget(QLabel(lab), k // 2, (k % 2) * 2); g.addWidget(s, k // 2, (k % 2) * 2 + 1)
        L.addLayout(g)
        rs = spin(it.get("rot", 0) or 0, -180, 180, 1, 1, " °"); rs.setWrapping(True); self.geo["rot"] = rs
        rs.valueChanged.connect(lambda v: win.set_prop("rot", v))
        L.addLayout(row(QLabel("Rotation"), rs, "stretch"))
        cf = swatch_combo(D, it.get("fill")); cf.activated.connect(lambda _: win.set_prop("fill", cf.currentData()))
        L.addLayout(row(QLabel("Fond"), cf, "stretch"))
        cs = swatch_combo(D, it.get("stroke")); cs.activated.connect(lambda _: win.set_prop("stroke", cs.currentData()))
        sw = spin(it.get("sw", .5), 0, 100, .25, 2, " pt"); sw.valueChanged.connect(lambda v: win.set_prop("sw", v))
        L.addLayout(row(QLabel("Contour"), cs, sw))
        if it["type"] == "text":
            st = D.d["stories"][it["story"]]; k = st["frames"].index(it["id"]) if it["id"] in st["frames"] else 0
            L.addWidget(h3("Texte"))
            ins = spin(it.get("inset") or 0, 0, 100); ins.valueChanged.connect(lambda v: win.set_prop("inset", v))
            L.addLayout(row(QLabel("Marge intérieure"), ins, "stretch"))
            b1 = QPushButton("Écrire sur la page"); b1.setProperty("primary", True); b1.clicked.connect(lambda: win.start_page_text(it["story"]))
            b2 = QPushButton("Éditeur de texte"); b2.clicked.connect(lambda: win.open_editor(it["story"]))
            L.addLayout(row(b1, b2, "stretch"))
            msg = (f"Bloc {k + 1} sur {len(st['frames'])} de ce texte chaîné. " if len(st["frames"]) > 1 else "Bloc seul. ")
            msg += ("<b style='color:#d33'>Texte en excès :</b> clique sur le carré rouge en bas à droite du bloc, puis sur un autre bloc ou dans une page pour faire couler la suite."
                    if st.get("_over") else "Pour faire couler le texte dans un autre bloc, clique sur le petit carré en bas à droite du bloc.")
            L.addWidget(hint(msg))
            if len(st["frames"]) > 1:
                b = QPushButton("Sortir ce bloc du chaînage"); b.clicked.connect(lambda: win.unlink_frame(it["id"])); L.addLayout(row(b, "stretch"))
        if it["type"] == "image":
            a = D.assets.get(it.get("asset"))
            L.addWidget(h3("Image"))
            b = QPushButton("Remplacer l’image" if a else "Choisir une image"); b.clicked.connect(lambda: win.pick_image(it["id"])); L.addLayout(row(b, "stretch"))
            if a:
                ppi = win.eff_ppi(it); col = "#d33" if ppi < 150 else "#d98a1a" if ppi < 300 else "#2a9a57"
                L.addWidget(hint(f"{a['name']} · {a['w']} × {a['h']} px<br>Résolution effective <b style='color:{col}'>{ppi} ppp</b> (vise 300 ppp pour l'impression)"))
                fit = QComboBox()
                for k2, n in [("cover", "Remplir le bloc"), ("contain", "Image entière"), ("fill", "Déformer")]: fit.addItem(n, k2)
                fit.setCurrentIndex(fit.findData(it.get("fit", "cover"))); fit.activated.connect(lambda _: win.set_prop("fit", fit.currentData()))
                L.addLayout(row(QLabel("Ajustement"), fit, "stretch"))
                for key, lab in [("fx", "Cadrage X"), ("fy", "Cadrage Y")]:
                    s = QSlider(Qt.Horizontal); s.setRange(0, 100); s.setValue(int(it.get(key, 50)))
                    s.sliderPressed.connect(win.commit)
                    s.valueChanged.connect(lambda v, key=key: win.set_prop(key, v, commit=False))
                    L.addLayout(row(QLabel(lab), s))
                b = QPushButton("Bloc à la taille de l’image"); b.clicked.connect(win.fit_frame_to_image); L.addLayout(row(b, "stretch"))
        self._arrange(L)

    def _arrange(self, L):
        L.addWidget(h3("Disposition"))
        g = QGridLayout()
        for k, (n, fn) in enumerate([("Premier plan", lambda: self.win.z_order(1)), ("Arrière-plan", lambda: self.win.z_order(-1)),
                                     ("Dupliquer", self.win.duplicate), ("Supprimer", self.win.delete_sel)]):
            b = QPushButton(n); b.clicked.connect(fn); g.addWidget(b, k // 2, k % 2)
        L.addLayout(g)

    def refresh_geometry(self):
        if len(self.win.sel) != 1 or not self.geo: return
        it = self.win.doc.item(self.win.sel[0])
        if not it: return
        for k, s in self.geo.items():
            s.blockSignals(True); s.setValue(it.get(k, 0) or 0); s.blockSignals(False)


# ---------------------------------------------------------------- Styles
class StylesPanel(Scroll):
    def __init__(self, win):
        super().__init__(); self.win = win; self.cur = "corps"; self.ccur = None

    def refresh(self):
        win, D = self.win, self.win.doc
        clear(self.lay); L = self.lay
        if not any(s["id"] == self.cur for s in D.d["styles"]): self.cur = D.d["styles"][0]["id"]
        lst = QListWidget(); lst.setMaximumHeight(170)
        for s in D.d["styles"]:
            it = QListWidgetItem(f"{s['name']}   ({s['size']:g}/{s['lead']:g})"); it.setData(Qt.UserRole, s["id"])
            f = QFont(s["font"]); f.setBold(s["weight"] >= 600); f.setItalic(s["ital"]); f.setPointSize(10); it.setFont(f)
            lst.addItem(it)
            if s["id"] == self.cur: lst.setCurrentItem(it)
        lst.itemClicked.connect(lambda it: (setattr(self, "cur", it.data(Qt.UserRole)), self.refresh()))
        L.addWidget(lst)
        bn, bd, bx = QPushButton("Nouveau"), QPushButton("Dupliquer"), QPushButton("Supprimer")
        bn.clicked.connect(lambda: self._new(False)); bd.clicked.connect(lambda: self._new(True)); bx.clicked.connect(self._del)
        bx.setEnabled(len(D.d["styles"]) > 1)
        L.addLayout(row(bn, bd, bx))
        s = D.style(self.cur)
        L.addWidget(h3("Réglages du style"))
        name = QLineEdit(s["name"]); name.editingFinished.connect(lambda: self.set("name", name.text() or s["name"]))
        L.addLayout(row(QLabel("Nom"), name))
        fc = QComboBox(); mine, sysf = fonts.all_families()
        for f in mine: fc.addItem(f)
        fc.insertSeparator(fc.count())
        for f in sysf: fc.addItem(f)
        if fc.findText(s["font"]) < 0: fc.addItem(s["font"])
        fc.setCurrentText(s["font"]); fc.setMaxVisibleItems(20)
        fc.activated.connect(lambda _: self.set("font", fc.currentText()))
        L.addLayout(row(QLabel("Police"), fc))
        bold = QCheckBox("Gras"); bold.setChecked(s["weight"] >= 600); bold.toggled.connect(lambda v: self.set("weight", 700 if v else 400))
        ital = QCheckBox("Italique"); ital.setChecked(s["ital"]); ital.toggled.connect(lambda v: self.set("ital", v))
        caps = QCheckBox("Capitales"); caps.setChecked(s.get("caps", False)); caps.toggled.connect(lambda v: self.set("caps", v))
        L.addLayout(row(bold, ital, caps, "stretch"))
        g = QGridLayout()
        fields = [("size", "Corps", " pt", 1, 999, .5), ("lead", "Interlignage", " pt", 1, 999, .5), ("sb", "Espace avant", " mm", 0, 999, .5),
                  ("sa", "Espace après", " mm", 0, 999, .5), ("ind", "Retrait 1re ligne", " mm", -999, 999, .5), ("track", "Approche", " ‰", -500, 2000, 5)]
        for k, (key, lab, suf, lo, hi, st) in enumerate(fields):
            sp = spin(s.get(key, 0), lo, hi, st, 1 if key != "track" else 0, suf)
            sp.valueChanged.connect(lambda v, key=key: self.set(key, v))
            lb = QLabel(lab); lb.setStyleSheet(MUTED)
            g.addWidget(lb, k, 0); g.addWidget(sp, k, 1)
        L.addLayout(g)
        al = QComboBox()
        for k2, n in [("left", "À gauche"), ("center", "Centré"), ("right", "À droite"), ("justify", "Justifié")]: al.addItem(n, k2)
        al.setCurrentIndex(al.findData(s["align"])); al.activated.connect(lambda _: self.set("align", al.currentData()))
        L.addLayout(row(QLabel("Alignement"), al, "stretch"))
        col = swatch_combo(D, s["color"], none=False); col.activated.connect(lambda _: self.set("color", col.currentData()))
        L.addLayout(row(QLabel("Couleur"), col, "stretch"))
        hy = QCheckBox("Césure (coupure des mots en fin de ligne)"); hy.setChecked(s.get("hyph", False)); hy.toggled.connect(lambda v: self.set("hyph", v))
        L.addWidget(hy)
        self.char_styles(L)
        L.addWidget(h3("Polices"))
        L.addWidget(hint("8 polices libres sont fournies. Tu peux aussi utiliser les polices de ton ordinateur, ou en importer (.ttf, .otf) : elles sont alors rangées dans le projet."))
        b = QPushButton("Importer une police…"); b.clicked.connect(win.import_font); L.addLayout(row(b, "stretch"))
        if D.d["customFonts"]:
            L.addWidget(hint("Importées : " + ", ".join(sorted({f["fam"] for f in D.d["customFonts"]}))))

    # ---------- styles de caractère ----------
    def char_styles(self, L):
        D = self.win.doc; cs_list = D.d.setdefault("charStyles", [])
        L.addWidget(h3("Styles de caractère"))
        L.addWidget(hint("Pour mettre en forme quelques mots dans un paragraphe (un nom en couleur, des capitales espacées…). "
                         "Sélectionne le texte puis choisis le style. Ce qui reste sur « garder » vient du style de paragraphe."))
        lst = QListWidget(); lst.setMaximumHeight(110)
        if not any(c["id"] == self.ccur for c in cs_list): self.ccur = cs_list[0]["id"] if cs_list else None
        for c in cs_list:
            it = QListWidgetItem(c["name"]); it.setData(Qt.UserRole, c["id"]); lst.addItem(it)
            if c["id"] == self.ccur: lst.setCurrentItem(it)
        lst.itemClicked.connect(lambda it: (setattr(self, "ccur", it.data(Qt.UserRole)), self.refresh()))
        L.addWidget(lst)
        bn, bx = QPushButton("Nouveau"), QPushButton("Supprimer")
        bn.clicked.connect(self._cs_new); bx.clicked.connect(self._cs_del); bx.setEnabled(bool(self.ccur))
        L.addLayout(row(bn, bx, "stretch"))
        c = D.char_style(self.ccur)
        if not c: return
        name = QLineEdit(c["name"]); name.editingFinished.connect(lambda: self.cset("name", name.text() or c["name"], True))
        L.addLayout(row(QLabel("Nom"), name))
        fc = QComboBox(); fc.addItem("(garder)", None)
        mine, sysf = fonts.all_families()
        for f in mine + sysf: fc.addItem(f, f)
        fc.setCurrentIndex(max(0, fc.findData(c.get("font")))); fc.setMaxVisibleItems(20)
        fc.activated.connect(lambda _: self.cset("font", fc.currentData()))
        L.addLayout(row(QLabel("Police"), fc))
        def tri(key, labels):
            cb = QComboBox()
            for v, n in labels: cb.addItem(n, v)
            cb.setCurrentIndex(max(0, cb.findData(c.get(key))))
            cb.activated.connect(lambda _: self.cset(key, cb.currentData()))
            return cb
        wb = tri("weight", [(None, "garder"), (400, "normal"), (700, "gras")])
        ib = tri("ital", [(None, "garder"), (False, "droit"), (True, "italique")])
        L.addLayout(row(QLabel("Graisse"), wb, QLabel("Style"), ib))
        cb = tri("caps", [(None, "garder"), (False, "normal"), (True, "capitales")])
        col = QComboBox(); col.addItem("(garder)", None)
        for s in D.d["swatches"]: col.addItem(chip(swatch_qcolor(D, s["id"])), s["name"], s["id"])
        col.setCurrentIndex(max(0, col.findData(c.get("color")))); col.activated.connect(lambda _: self.cset("color", col.currentData()))
        L.addLayout(row(QLabel("Casse"), cb, QLabel("Couleur"), col))
        sz = spin(c.get("size") or 0, 0, 999, .5, 1, " pt"); sz.setSpecialValueText("garder")
        sz.valueChanged.connect(lambda v: self.cset("size", v or None))
        tr = spin(c["track"] if c.get("track") is not None else -501, -501, 2000, 5, 0, " ‰"); tr.setSpecialValueText("garder")
        tr.valueChanged.connect(lambda v: self.cset("track", None if v <= -501 else v))
        L.addLayout(row(QLabel("Corps"), sz, QLabel("Approche"), tr))
        un = QCheckBox("Souligné"); un.setChecked(bool(c.get("under"))); un.toggled.connect(lambda v: self.cset("under", v))
        L.addWidget(un)

    def cset(self, key, v, full=False):
        c = self.win.doc.char_style(self.ccur)
        if c is None or c.get(key) == v: return
        self.win.commit(merge=f"cs:{self.ccur}:{key}")
        c[key] = v; self.win.styles_changed()
        if full: self.refresh()

    def _cs_new(self):
        from .model import uid
        self.win.commit()
        c = {"id": uid("cs"), "name": "Nouveau style car.", "font": None, "weight": 700, "ital": None, "size": None, "color": None, "track": None, "caps": None, "under": False}
        self.win.doc.d.setdefault("charStyles", []).append(c); self.ccur = c["id"]; self.win.styles_changed(); self.refresh()

    def _cs_del(self):
        D = self.win.doc
        if not self.ccur: return
        self.win.commit()
        cid = self.ccur
        D.d["charStyles"] = [c for c in D.d["charStyles"] if c["id"] != cid]
        from .model import para_chars, chars_para
        for st in D.d["stories"].values():
            for p in st["paras"]:
                if cid in p["h"]:
                    t, a = para_chars(p["h"]); p["h"] = chars_para(t, [(x[0], x[1], None if x[2] == cid else x[2]) for x in a])
        self.ccur = None; self.win.styles_changed(); self.refresh()

    def set(self, key, v):
        s = self.win.doc.style(self.cur)
        if s.get(key) == v: return
        self.win.commit(merge=f"style:{self.cur}:{key}")
        s[key] = v
        self.win.styles_changed()
        if key in ("name", "font", "weight", "ital", "size", "lead"):
            self.refresh()

    def _new(self, dup):
        from .model import uid
        D = self.win.doc; self.win.commit()
        src = D.style(self.cur if dup else "corps")
        s = dict(src); s["id"] = uid("st"); s["name"] = (src["name"] + " copie") if dup else "Nouveau style"
        D.d["styles"].append(s); self.cur = s["id"]; self.win.styles_changed(); self.refresh()

    def _del(self):
        D = self.win.doc
        if len(D.d["styles"]) < 2: return
        self.win.commit()
        D.d["styles"] = [s for s in D.d["styles"] if s["id"] != self.cur]
        rep = D.d["styles"][0]["id"]
        for st in D.d["stories"].values():
            for p in st["paras"]:
                if p["s"] == self.cur: p["s"] = rep
        self.cur = rep; self.win.styles_changed(); self.refresh()


# ---------------------------------------------------------------- Nuancier
class SwatchesPanel(Scroll):
    def __init__(self, win):
        super().__init__(); self.win = win; self.cur = "noir"

    def refresh(self):
        win, D = self.win, self.win.doc
        clear(self.lay); L = self.lay
        if not D.swatch(self.cur): self.cur = "noir"
        lst = QListWidget(); lst.setMaximumHeight(190)
        for s in D.d["swatches"]:
            val = f"C{s['c']:g} M{s['m']:g} J{s['y']:g} N{s['k']:g}" if s["mode"] == "cmyk" else s.get("hex", "")
            it = QListWidgetItem(chip(swatch_qcolor(D, s["id"])), f"{s['name']}   {val}"); it.setData(Qt.UserRole, s["id"]); lst.addItem(it)
            if s["id"] == self.cur: lst.setCurrentItem(it)
        lst.itemClicked.connect(lambda it: (setattr(self, "cur", it.data(Qt.UserRole)), self.refresh()))
        L.addWidget(lst)
        bn, bx = QPushButton("Nouvelle couleur"), QPushButton("Supprimer")
        bn.clicked.connect(self._new); bx.clicked.connect(self._del); bx.setEnabled(self.cur not in ("noir", "papier"))
        L.addLayout(row(bn, bx))
        s = D.swatch(self.cur)
        L.addWidget(h3("Couleur sélectionnée"))
        name = QLineEdit(s["name"]); name.editingFinished.connect(lambda: self.set("name", name.text() or s["name"], True))
        L.addLayout(row(QLabel("Nom"), name))
        mode = QComboBox(); mode.addItem("CMJN (impression)", "cmyk"); mode.addItem("RVB (écran)", "rgb")
        mode.setCurrentIndex(0 if s["mode"] == "cmyk" else 1); mode.activated.connect(lambda _: self._mode(mode.currentData()))
        L.addLayout(row(QLabel("Mode"), mode, "stretch"))
        if s["mode"] == "cmyk":
            for key, lab in [("c", "Cyan"), ("m", "Magenta"), ("y", "Jaune"), ("k", "Noir")]:
                sl = QSlider(Qt.Horizontal); sl.setRange(0, 100); sl.setValue(int(s[key]))
                sp = QSpinBox(); sp.setRange(0, 100); sp.setValue(int(s[key])); sp.setSuffix(" %")
                sl.valueChanged.connect(sp.setValue); sp.valueChanged.connect(sl.setValue)
                sp.valueChanged.connect(lambda v, key=key: self.set(key, v))
                lb = QLabel(lab); lb.setFixedWidth(60)
                L.addLayout(row(lb, sl, sp))
        else:
            b = QPushButton(s.get("hex", "#000000")); b.setStyleSheet(f"background:{s.get('hex')};color:{'#fff' if QColor(s.get('hex')).lightness() < 128 else '#000'}")
            b.clicked.connect(self._pick); L.addLayout(row(QLabel("Couleur"), b, "stretch"))
        L.addWidget(hint("Les couleurs CMJN partent telles quelles dans le PDF (pratique pour l'imprimeur). À l'écran, c'est une simulation. Les images restent en RVB."))

    def set(self, key, v, full=False):
        s = self.win.doc.swatch(self.cur)
        if s.get(key) == v: return
        self.win.commit(merge=f"sw:{self.cur}:{key}")
        s[key] = v; self.win.styles_changed()
        if full: self.refresh()

    def _mode(self, m):
        s = self.win.doc.swatch(self.cur)
        if s["mode"] == m: return
        self.win.commit()
        if m == "rgb": s["hex"] = swatch_qcolor(self.win.doc, s["id"]).toRgb().name()
        else:
            c = QColor(s.get("hex", "#000")).toCmyk()
            s.update(c=round(c.cyanF() * 100), m=round(c.magentaF() * 100), y=round(c.yellowF() * 100), k=round(c.blackF() * 100))
        s["mode"] = m; self.win.styles_changed(); self.refresh()

    def _pick(self):
        s = self.win.doc.swatch(self.cur)
        c = QColorDialog.getColor(QColor(s.get("hex", "#000")), self, "Couleur")
        if c.isValid(): self.set("hex", c.name(), True)

    def _new(self):
        from .model import uid
        self.win.commit()
        s = {"id": uid("c"), "name": f"Couleur {len(self.win.doc.d['swatches']) + 1}", "mode": "cmyk", "c": 0, "m": 50, "y": 100, "k": 0, "hex": "#ff8000"}
        self.win.doc.d["swatches"].append(s); self.cur = s["id"]; self.refresh()

    def _del(self):
        D = self.win.doc
        if self.cur in ("noir", "papier"): return
        self.win.commit()
        D.d["swatches"] = [s for s in D.d["swatches"] if s["id"] != self.cur]
        for it in D.d["items"]:
            if it.get("fill") == self.cur: it["fill"] = None
            if it.get("stroke") == self.cur: it["stroke"] = None
        for s in D.d["styles"]:
            if s["color"] == self.cur: s["color"] = "noir"
        self.cur = "noir"; self.win.styles_changed(); self.refresh()


# ---------------------------------------------------------------- Contrôle
class CheckPanel(Scroll):
    def __init__(self, win):
        super().__init__(); self.win = win

    def issues(self):
        D, d = self.win.doc, self.win.doc.d
        out = []
        for st in d["stories"].values():
            if st.get("_over") and st["frames"]:
                out.append(("err", "Texte en excès : la fin du texte ne rentre pas dans les blocs.", st["frames"][-1]))
        for it in d["items"]:
            if it["type"] == "image":
                if it.get("asset") not in D.assets:
                    out.append(("warn", "Bloc image vide (il ne sera pas imprimé).", it["id"]))
                else:
                    v = self.win.eff_ppi(it)
                    if v < 300: out.append(("err" if v < 150 else "warn", f"Image {D.assets[it['asset']]['name']} à {v} ppp (300 conseillés).", it["id"]))
            if "p" in it["on"]:
                b = d["bleed"]; bb = item_bounds(it)
                outside = bb.left() >= d["w"] or bb.top() >= d["h"] or bb.right() <= 0 or bb.bottom() <= 0
                ex = bb.left() < -b - .01 or bb.top() < -b - .01 or bb.right() > d["w"] + b + .01 or bb.bottom() > d["h"] + b + .01
                if outside: out.append(("warn", "Bloc hors de la page : il ne sera pas imprimé.", it["id"]))
                elif ex and it["type"] != "text": out.append(("warn", "Bloc qui dépasse les fonds perdus : il sera coupé.", it["id"]))
        if d["facing"] and len(d["pages"]) % 4:
            out.append(("warn", f"{len(d['pages'])} pages : pour une brochure en piqûre à cheval, il faut un multiple de 4.", None))
        return out

    def refresh(self):
        clear(self.lay); L = self.lay
        L.addWidget(QLabel("<b>Contrôle avant impression</b>"))
        iss = self.issues()
        if not iss:
            l = QLabel("Tout est bon ✓"); l.setStyleSheet("padding:6px;border-left:3px solid #3bb36b;background:#fff"); L.addWidget(l)
        for lvl, txt, iid in iss:
            b = QPushButton(txt); b.setStyleSheet(f"text-align:left;padding:6px;border:0;border-left:3px solid {'#d2462e' if lvl == 'err' else '#e9a23b'};background:#fff")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            lbl = QLabel(txt); lbl.setWordWrap(True)
            b.setText(""); bl = QHBoxLayout(b); bl.setContentsMargins(8, 4, 4, 4); bl.addWidget(lbl); b.setMinimumHeight(40)
            if iid: b.clicked.connect(lambda _=0, iid=iid: self.win.goto_item(iid))
            L.addWidget(b)
        L.addWidget(hint("Rouge = à corriger, orange = à vérifier. Clique sur un point pour aller au bloc."))
        return sum(1 for l, *_ in iss if l == "err")
