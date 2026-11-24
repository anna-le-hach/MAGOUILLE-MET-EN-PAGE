"""Éditeur de texte : un paragraphe = un bloc Qt, le style est rangé dans le format du bloc."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QComboBox, QPushButton, QLabel, QFileDialog
from PySide6.QtGui import QTextCursor, QTextBlockFormat, QTextCharFormat, QFont, QTextFormat, QColor
from PySide6.QtCore import Qt, QTimer, Signal
from .model import para_chars, chars_para, FAUX_TEXTE
from .textflow import swatch_qcolor

P_STYLE = QTextFormat.UserProperty + 1
P_B = QTextFormat.UserProperty + 2
P_I = QTextFormat.UserProperty + 3
P_CS = QTextFormat.UserProperty + 4


class _Edit(QTextEdit):
    def insertFromMimeData(self, src):
        if src.hasText():
            self.textCursor().insertText(src.text().replace("\r", ""))


class StoryEditor(QWidget):
    changed = Signal(str, list)   # story id, paragraphes
    closed = Signal()

    def __init__(self, win):
        super().__init__()
        self.win, self.sid, self._loading = win, None, False
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 6, 6, 6)
        head = QHBoxLayout()
        self.info = QLabel(""); self.info.setStyleSheet("color:#7a766e")
        bclose = QPushButton("Fermer"); bclose.clicked.connect(self.close_editor)
        head.addWidget(QLabel("<b>Éditeur de texte</b>")); head.addWidget(self.info); head.addStretch(); head.addWidget(bclose)
        lay.addLayout(head)
        bar = QHBoxLayout()
        self.combo = QComboBox(); self.combo.setToolTip("Style du paragraphe"); self.combo.activated.connect(self.apply_style)
        bar.addWidget(self.combo, 1)
        self.ccombo = QComboBox(); self.ccombo.setToolTip("Style de caractère (sur la sélection)"); self.ccombo.activated.connect(self.apply_char_style)
        bar.addWidget(self.ccombo, 1)
        for txt, tip, fn in [("G", "Gras (Ctrl+B)", self.toggle_bold), ("I", "Italique (Ctrl+I)", self.toggle_italic),
                             ("N° page", "Insérer le numéro de page", lambda: self.ed.insertPlainText("{n}")),
                             ("Faux texte", "Remplir avec du faux texte", self.lorem), (".txt", "Importer un fichier texte", self.import_txt)]:
            b = QPushButton(txt); b.setToolTip(tip); b.clicked.connect(fn); b.setFocusPolicy(Qt.NoFocus)
            if txt == "G": f = b.font(); f.setBold(True); b.setFont(f)
            if txt == "I": f = b.font(); f.setItalic(True); b.setFont(f)
            bar.addWidget(b)
        lay.addLayout(bar)
        self.ed = _Edit(); self.ed.setAcceptRichText(False)
        self.ed.document().setDocumentMargin(12)
        lay.addWidget(self.ed, 1)
        foot = QLabel("Entrée = nouveau paragraphe · Maj+Entrée = retour à la ligne · le style s'applique aux paragraphes sélectionnés")
        foot.setWordWrap(True); foot.setStyleSheet("color:#7a766e;font-size:11px"); lay.addWidget(foot)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(200); self.timer.timeout.connect(self.emit_change)
        self.ed.textChanged.connect(lambda: None if self._loading else self.timer.start())
        self.ed.cursorPositionChanged.connect(self.sync_combo)
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("Ctrl+B"), self.ed, self.toggle_bold)
        QShortcut(QKeySequence("Ctrl+I"), self.ed, self.toggle_italic)
        QShortcut(QKeySequence("Escape"), self.ed, self.close_editor)

    @property
    def D(self): return self.win.doc

    def refresh_styles(self):
        cur = self.combo.currentData()
        self.combo.blockSignals(True); self.combo.clear()
        for s in self.D.d["styles"]:
            self.combo.addItem(s["name"], s["id"])
        self.combo.blockSignals(False)
        self.ccombo.blockSignals(True); self.ccombo.clear(); self.ccombo.addItem("Aucun style car.", "")
        for c in self.D.d.get("charStyles", []):
            self.ccombo.addItem(c["name"], c["id"])
        self.ccombo.blockSignals(False)
        if self.sid:
            self._loading = True
            b = self.ed.document().begin()
            while b.isValid():
                self.restyle_block(b); b = b.next()
            self._loading = False
        self.sync_combo()

    def load(self, sid):
        self.sid = sid
        st = self.D.d["stories"][sid]
        self._loading = True
        self.ed.clear()
        cur = QTextCursor(self.ed.document())
        for k, p in enumerate(st["paras"]):
            bf = QTextBlockFormat(); bf.setProperty(P_STYLE, p["s"]); bf.setBottomMargin(5)
            if k == 0: cur.setBlockFormat(bf)
            else: cur.insertBlock(bf)
            text, attrs = para_chars(p["h"])
            j = 0
            while j < len(text):
                k2 = j
                while k2 < len(text) and attrs[k2] == attrs[j]: k2 += 1
                cf = QTextCharFormat(); cf.setProperty(P_B, attrs[j][0]); cf.setProperty(P_I, attrs[j][1]); cf.setProperty(P_CS, attrs[j][2] or "")
                cur.insertText(text[j:k2], self.style_visual(p["s"], cf)); j = k2
        self._loading = False
        self.refresh_styles()
        n = len(st["frames"])
        self.info.setText(f"{n} blocs chaînés" if n > 1 else "1 bloc")
        self.ed.moveCursor(QTextCursor.End); self.ed.setFocus()

    def style_visual(self, sid, cf):
        s = self.D.style(sid)
        cf.setFontFamilies([s["font"]])
        cf.setFontPointSize(max(9.0, min(20.0, s["size"])))
        cf.setFontWeight(QFont.Bold if (cf.property(P_B) or s["weight"] >= 600) else QFont.Normal)
        cf.setFontItalic(bool(cf.property(P_I) or s["ital"]))
        cf.setForeground(swatch_qcolor(self.D, s["color"]))
        cf.setFontCapitalization(QFont.AllUppercase if s.get("caps") else QFont.MixedCase)
        c = self.D.char_style(cf.property(P_CS)) if cf.property(P_CS) else None
        cf.setFontUnderline(bool(c and c.get("under")))
        if c:
            if c.get("font"): cf.setFontFamilies([c["font"]])
            if c.get("weight") is not None and not cf.property(P_B): cf.setFontWeight(QFont.Bold if c["weight"] >= 600 else QFont.Normal)
            if c.get("ital") is not None and not cf.property(P_I): cf.setFontItalic(bool(c["ital"]))
            if c.get("color"): cf.setForeground(swatch_qcolor(self.D, c["color"]))
            if c.get("caps") is not None: cf.setFontCapitalization(QFont.AllUppercase if c["caps"] else QFont.MixedCase)
            cf.setBackground(QColor(255, 240, 200))
        else:
            cf.setBackground(Qt.transparent)
        return cf

    def restyle_block(self, block):
        sid = block.blockFormat().property(P_STYLE) or "corps"
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            c = QTextCursor(self.ed.document()); c.setPosition(frag.position()); c.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
            cf = frag.charFormat(); c.setCharFormat(self.style_visual(sid, cf))
            it += 1
        # format courant pour la frappe dans un paragraphe vide
        if block.length() <= 1:
            c = QTextCursor(block); cf = QTextCharFormat(); c.setBlockCharFormat(self.style_visual(sid, cf))

    def selected_blocks(self):
        c = self.ed.textCursor(); doc = self.ed.document()
        b, e = doc.findBlock(c.selectionStart()), doc.findBlock(c.selectionEnd())
        out = []
        while b.isValid():
            out.append(b)
            if b == e: break
            b = b.next()
        return out

    def sync_combo(self):
        b = self.ed.textCursor().block()
        sid = b.blockFormat().property(P_STYLE) or "corps"
        i = self.combo.findData(sid)
        if i >= 0:
            self.combo.blockSignals(True); self.combo.setCurrentIndex(i); self.combo.blockSignals(False)
        cf = self.ed.currentCharFormat()
        j = self.ccombo.findData(cf.property(P_CS) or "")
        self.ccombo.blockSignals(True); self.ccombo.setCurrentIndex(max(0, j)); self.ccombo.blockSignals(False)
        if True:
            self.ed.setCurrentCharFormat(self.style_visual(sid, cf))

    def apply_style(self, _=None):
        sid = self.combo.currentData()
        for b in self.selected_blocks():
            c = QTextCursor(b); bf = b.blockFormat(); bf.setProperty(P_STYLE, sid); c.setBlockFormat(bf)
            self.restyle_block(b)
        self.emit_change(); self.ed.setFocus()

    def _toggle(self, prop):
        c = self.ed.textCursor()
        if not c.hasSelection():
            cf = self.ed.currentCharFormat(); cf.setProperty(prop, not cf.property(prop))
            sid = c.block().blockFormat().property(P_STYLE) or "corps"
            self.ed.setCurrentCharFormat(self.style_visual(sid, cf)); return
        on = not c.charFormat().property(prop)
        start, end = c.selectionStart(), c.selectionEnd()
        doc = self.ed.document()
        pos = start
        while pos < end:
            cc = QTextCursor(doc); cc.setPosition(pos); cc.setPosition(pos + 1, QTextCursor.KeepAnchor)
            cf = cc.charFormat(); cf.setProperty(prop, on)
            sid = cc.block().blockFormat().property(P_STYLE) or "corps"
            cc.setCharFormat(self.style_visual(sid, cf)); pos += 1
        self.emit_change()

    def apply_char_style(self, _=None):
        cid = self.ccombo.currentData() or ""
        c = self.ed.textCursor()
        if not c.hasSelection():
            cf = self.ed.currentCharFormat(); cf.setProperty(P_CS, cid)
            sid = c.block().blockFormat().property(P_STYLE) or "corps"
            self.ed.setCurrentCharFormat(self.style_visual(sid, cf)); self.ed.setFocus(); return
        doc = self.ed.document(); pos, end = c.selectionStart(), c.selectionEnd()
        while pos < end:
            cc = QTextCursor(doc); cc.setPosition(pos); cc.setPosition(pos + 1, QTextCursor.KeepAnchor)
            cf = cc.charFormat(); cf.setProperty(P_CS, cid)
            sid = cc.block().blockFormat().property(P_STYLE) or "corps"
            cc.setCharFormat(self.style_visual(sid, cf)); pos += 1
        self.emit_change(); self.ed.setFocus()

    def toggle_bold(self): self._toggle(P_B)
    def toggle_italic(self): self._toggle(P_I)

    def lorem(self):
        c = QTextCursor(self.ed.document()); c.movePosition(QTextCursor.End)
        for t in FAUX_TEXTE:
            bf = QTextBlockFormat(); bf.setProperty(P_STYLE, "corps"); bf.setBottomMargin(5)
            if self.ed.document().characterCount() > 1: c.insertBlock(bf)
            else: c.setBlockFormat(bf)
            c.insertText(t, self.style_visual("corps", QTextCharFormat()))
        self.emit_change()

    def import_txt(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Importer un texte", "", "Texte (*.txt)")
        if not fn: return
        with open(fn, encoding="utf-8", errors="replace") as f:
            lines = [l.strip() for l in f.read().replace("\r", "").split("\n") if l.strip()]
        c = QTextCursor(self.ed.document()); c.movePosition(QTextCursor.End)
        for l in lines:
            bf = QTextBlockFormat(); bf.setProperty(P_STYLE, "corps"); bf.setBottomMargin(5)
            if self.ed.document().characterCount() > 1: c.insertBlock(bf)
            else: c.setBlockFormat(bf)
            c.insertText(l, self.style_visual("corps", QTextCharFormat()))
        self.emit_change()

    def read(self):
        paras, b = [], self.ed.document().begin()
        while b.isValid():
            sid = b.blockFormat().property(P_STYLE)
            if not sid or not any(s["id"] == sid for s in self.D.d["styles"]):
                sid = paras[-1]["s"] if paras else "corps"
            text, attrs, it = "", [], b.begin()
            while not it.atEnd():
                fr = it.fragment(); cf = fr.charFormat()
                a = (bool(cf.property(P_B)), bool(cf.property(P_I)), cf.property(P_CS) or None)
                text += fr.text(); attrs += [a] * len(fr.text()); it += 1
            paras.append({"s": sid, "h": chars_para(text, attrs)})
            b = b.next()
        return paras or [{"s": "corps", "h": ""}]

    def emit_change(self):
        if self.sid and self.sid in self.D.d["stories"]:
            self.changed.emit(self.sid, self.read())

    def close_editor(self):
        if self.timer.isActive():
            self.timer.stop(); self.emit_change()
        self.closed.emit()
