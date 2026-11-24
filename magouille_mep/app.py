"""Fenêtre principale de Magouille met en page."""
import os, sys, json, base64, time, re
from PySide6.QtWidgets import (QApplication, QMainWindow, QScrollArea, QDockWidget, QTabWidget, QToolBar, QLabel, QFileDialog,
                               QMessageBox, QWidget, QStyleFactory, QProgressDialog)
from PySide6.QtGui import QDesktopServices, QAction, QActionGroup, QIcon, QPixmap, QPainter, QColor, QPen, QImage, QKeySequence, QPalette, QFont, QPolygonF
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QBuffer, QByteArray, QIODevice, QPointF, QRectF, QUrl
from . import APP_NAME, __version__, fonts
from .model import Doc, new_doc, example_doc, placement_key, uid, r2, MM
from .render import Renderer
from .canvas import Canvas, PX_MM, clamp
from .panels import PagesPanel, PropsPanel, StylesPanel, SwatchesPanel, CheckPanel
from .editor import StoryEditor
from .pagetext import PageText
from .render import item_bounds
from .dialogs import Welcome, SetupDialog, ExportDialog, HelpDialog

TOOL_HINT = {"select": "Sélection : clique pour choisir, glisse pour déplacer", "text": "Texte : trace un bloc, ou clique dans un bloc pour écrire",
             "image": "Image : trace un bloc puis choisis une image", "rect": "Rectangle : trace la forme", "ellipse": "Ellipse : trace la forme"}


def tool_icon(kind):
    pm = QPixmap(40, 40); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(QColor(40, 40, 40), 2.4)); p.setBrush(QColor(40, 40, 40))
    if kind == "select":
        p.drawPolygon(QPolygonF([QPointF(11, 6), QPointF(30, 21), QPointF(21, 23), QPointF(16, 33)]))
    elif kind == "text":
        f = QFont("Serif"); f.setPixelSize(30); f.setBold(True); p.setFont(f); p.drawText(QRectF(0, 0, 40, 40), Qt.AlignCenter, "T")
    elif kind == "image":
        p.setBrush(Qt.NoBrush); p.drawRect(8, 8, 24, 24); p.drawLine(8, 8, 32, 32); p.drawLine(32, 8, 8, 32)
    elif kind == "rect":
        p.drawRect(8, 11, 24, 18)
    elif kind == "ellipse":
        p.drawEllipse(7, 11, 26, 18)
    p.end()
    return QIcon(pm)


def app_icon():
    """Icône : Magouille le moineau devant une page."""
    path = os.path.join(fonts.resource_dir(), "icone.png")
    if os.path.exists(path):
        return QIcon(path)
    return QIcon()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME); self.setWindowIcon(app_icon()); self.resize(1400, 880)
        self.doc = Doc(new_doc()); self.renderer = Renderer(self.doc)
        self.sel, self.tool, self.preview, self.link_from = [], "select", False, None
        self.cur_page = self.doc.d["pages"][0]["id"]
        self.undo_stack, self.redo_stack, self._merge = [], [], (None, 0)
        self.path, self.dirty, self.editing, self._edsnap = None, False, None, None
        self.page_text = None
        # centre
        self.canvas = Canvas(self)
        self.scroll = QScrollArea(); self.scroll.setWidget(self.canvas); self.scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.scroll.setStyleSheet("QScrollArea{background:#ecebe7;border:0}")
        self.setCentralWidget(self.scroll)
        # panneaux
        self.pages = PagesPanel(self)
        dl = QDockWidget("Pages", self); dl.setWidget(self.pages); dl.setFeatures(QDockWidget.DockWidgetMovable); dl.setMinimumWidth(200)
        self.addDockWidget(Qt.LeftDockWidgetArea, dl)
        self.tabs = QTabWidget()
        self.props, self.styles, self.swatches, self.check = PropsPanel(self), StylesPanel(self), SwatchesPanel(self), CheckPanel(self)
        for w, n in [(self.props, "Propriétés"), (self.styles, "Styles"), (self.swatches, "Nuancier"), (self.check, "Contrôle")]:
            self.tabs.addTab(w, n)
        self.tabs.currentChanged.connect(lambda _: self.refresh_panels())
        dr = QDockWidget("Réglages", self); dr.setWidget(self.tabs); dr.setFeatures(QDockWidget.DockWidgetMovable); dr.setMinimumWidth(300)
        self.addDockWidget(Qt.RightDockWidgetArea, dr)
        self.editor = StoryEditor(self)
        self.editor.changed.connect(self.story_changed); self.editor.closed.connect(self.close_editor)
        self.ed_dock = QDockWidget("Texte", self); self.ed_dock.setWidget(self.editor); self.ed_dock.setFeatures(QDockWidget.DockWidgetMovable)
        self.ed_dock.setMinimumWidth(420)
        self.addDockWidget(Qt.RightDockWidgetArea, self.ed_dock); self.splitDockWidget(self.ed_dock, dr, Qt.Horizontal); self.ed_dock.hide()
        self._build_actions()
        # barre d'état
        self.st_tool, self.st_pos, self.st_msg = QLabel(), QLabel(), QLabel()
        for w in (self.st_tool, self.st_pos): self.statusBar().addWidget(w)
        self.statusBar().addPermanentWidget(self.st_msg)
        self.canvas.posChanged.connect(self.st_pos.setText)
        self.autosave_timer = QTimer(self); self.autosave_timer.setSingleShot(True); self.autosave_timer.setInterval(1500)
        self.autosave_timer.timeout.connect(self.autosave)
        self.set_tool("select")
        self.refresh()

    # ------------------------------------------------------------ actions
    def _act(self, text, fn, shortcut=None, tip=None, checkable=False):
        a = QAction(text, self); a.triggered.connect(fn)
        if shortcut: a.setShortcut(QKeySequence(shortcut))
        if tip: a.setToolTip(tip)
        a.setCheckable(checkable); return a

    def _build_actions(self):
        A = self._act
        self.a_new = A("Nouveau", self.new_dialog, "Ctrl+N"); self.a_open = A("Ouvrir…", self.open_dialog, "Ctrl+O")
        self.a_save = A("Enregistrer", self.save, "Ctrl+S"); self.a_saveas = A("Enregistrer sous…", self.save_as, "Ctrl+Shift+S")
        self.a_export = A("Exporter PDF…", self.export_dialog, "Ctrl+E"); self.a_setup = A("Format du document…", self.setup_dialog)
        self.a_undo = A("Annuler", self.undo, "Ctrl+Z"); self.a_redo = A("Rétablir", self.redo, "Ctrl+Shift+Z")
        self.a_dup = A("Dupliquer", self.duplicate, "Ctrl+D"); self.a_all = A("Tout sélectionner (planche)", self.select_all, "Ctrl+A")
        self.a_prev = A("Aperçu", self.toggle_preview, None, "Aperçu sans repères (W)", True)
        self.a_zin = A("+", lambda: self.set_zoom(self.canvas.zoom * 1.25), "Ctrl++", "Zoom avant")
        self.a_zout = A("−", lambda: self.set_zoom(self.canvas.zoom / 1.25), "Ctrl+-", "Zoom arrière")
        self.a_fit = A("Ajuster", self.zoom_fit, "Ctrl+0", "Ajuster à la fenêtre")
        self.a_help = A("Aide", lambda: HelpDialog(self).exec(), "F1")
        mb = self.menuBar()
        m = mb.addMenu("Fichier")
        for a in (self.a_new, self.a_open, self.a_save, self.a_saveas, None, self.a_export, None, self.a_setup, None):
            m.addSeparator() if a is None else m.addAction(a)
        m.addAction(A("Quitter", self.close, "Ctrl+Q"))
        m = mb.addMenu("Édition")
        for a in (self.a_undo, self.a_redo, None, self.a_dup, self.a_all):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("Affichage")
        for a in (self.a_prev, None, self.a_zin, self.a_zout, self.a_fit):
            m.addSeparator() if a is None else m.addAction(a)
        m = mb.addMenu("Aide"); m.addAction(self.a_help)
        m.addAction(A("Soutenir le projet ☕", lambda: QDesktopServices.openUrl(QUrl("https://ko-fi.com/annatabutiaux"))))
        m.addAction(A("À propos", lambda: QMessageBox.about(self, APP_NAME, f"<b>{APP_NAME}</b> {__version__}<br>Petit logiciel de mise en page libre (licence MIT).<br>Polices : SIL Open Font License.<br><br>Il est et restera gratuit. Si tu veux m'offrir un café : <a href='https://ko-fi.com/annatabutiaux'>ko-fi.com/annatabutiaux</a>")))
        tb = QToolBar("Fichier"); tb.setMovable(False); tb.setToolButtonStyle(Qt.ToolButtonTextOnly); self.addToolBar(tb)
        for a in (self.a_new, self.a_open, self.a_save, None, self.a_setup, self.a_export, None, self.a_undo, self.a_redo, None, self.a_prev, self.a_zout):
            tb.addSeparator() if a is None else tb.addAction(a)
        self.zoom_lbl = QLabel("100 %"); self.zoom_lbl.setMinimumWidth(50); self.zoom_lbl.setAlignment(Qt.AlignCenter); tb.addWidget(self.zoom_lbl)
        tb.addAction(self.a_zin); tb.addAction(self.a_fit); tb.addSeparator(); tb.addAction(self.a_help)
        w = tb.widgetForAction(self.a_export)
        if w: w.setStyleSheet("background:#d2462e;color:white;border-radius:5px;padding:3px 10px")
        tt = QToolBar("Outils"); tt.setMovable(False); tt.setIconSize(tt.iconSize() * 1.1); self.addToolBar(Qt.LeftToolBarArea, tt)
        grp = QActionGroup(self); self.tool_actions = {}
        for k, n, key in [("select", "Sélection", "V"), ("text", "Bloc texte", "T"), ("image", "Bloc image", "F"), ("rect", "Rectangle", "M"), ("ellipse", "Ellipse", "L")]:
            a = QAction(tool_icon(k), f"{n} ({key})", self); a.setCheckable(True); a.triggered.connect(lambda _=0, k=k: self.set_tool(k))
            grp.addAction(a); tt.addAction(a); self.tool_actions[k] = a

    # ------------------------------------------------------------ rafraîchissement
    def refresh(self, reflow=True):
        if self.page_text and self.page_text.sid not in self.doc.d["stories"]:
            self.page_text.stop(); self.page_text = None
        self.renderer.layout()
        if reflow:
            self.renderer.reflow(); self.renderer.invalidate_masters()
        self.canvas.resize_board()
        self.refresh_panels()
        self.pages.refresh()
        self.update_title()

    def refresh_panels(self):
        self.props.refresh()
        i = self.tabs.currentIndex()
        if i == 1: self.styles.refresh()
        if i == 2: self.swatches.refresh()
        n = self.check.refresh()
        self.tabs.setTabText(3, f"Contrôle ({n})" if n else "Contrôle")

    def props_refresh_geometry(self):
        self.props.refresh_geometry()

    def update_title(self):
        self.setWindowTitle(f"{'• ' if self.dirty else ''}{self.doc.d['name']} — {APP_NAME}")
        self.a_undo.setEnabled(bool(self.undo_stack)); self.a_redo.setEnabled(bool(self.redo_stack))

    def msg(self, t, ms=4000):
        self.st_msg.setText(t)
        QTimer.singleShot(ms, lambda: self.st_msg.setText("") if self.st_msg.text() == t else None)

    # ------------------------------------------------------------ historique
    def snapshot(self):
        return json.dumps(self.doc.d)

    def commit(self, merge=None):
        now = time.time()
        if merge and self._merge[0] == merge and now - self._merge[1] < 1.2:
            self._merge = (merge, now); return
        self._merge = (merge, now)
        self.undo_stack.append(self.snapshot()); self.undo_stack = self.undo_stack[-80:]
        self.redo_stack.clear(); self.dirty = True; self.autosave_timer.start(); self.update_title()

    def commit_before(self, origs):
        cur = [dict(self.doc.item(o["id"])) for o in origs]
        for o in origs: self.doc.item(o["id"]).update(o)
        self.commit()
        for c in cur: self.doc.item(c["id"]).update(c)

    def _restore(self, s):
        self.doc.d = json.loads(s)
        self.sel = [i for i in self.sel if self.doc.item(i)]
        if self.editing and self.editing not in self.doc.d["stories"]: self.close_editor(silent=True)
        if self.renderer.mode == "master" and not any(m["id"] == self.renderer.master for m in self.doc.d["masters"]):
            self.renderer.mode = "pages"
        if not any(p["id"] == self.cur_page for p in self.doc.d["pages"]): self.cur_page = self.doc.d["pages"][0]["id"]
        if self.page_text and self.page_text.sid in self.doc.d["stories"]: self.page_text.clamp()
        self.dirty = True; self.refresh()
        if self.editing: self.editor.load(self.editing)

    def undo(self):
        if not self.undo_stack: return
        self.redo_stack.append(self.snapshot()); self._restore(self.undo_stack.pop()); self._merge = (None, 0)

    def redo(self):
        if not self.redo_stack: return
        self.undo_stack.append(self.snapshot()); self._restore(self.redo_stack.pop())

    # ------------------------------------------------------------ outils et sélection
    def set_tool(self, t):
        self.tool = t; self.tool_actions[t].setChecked(True); self.st_tool.setText(TOOL_HINT[t])

    def select(self, ids):
        if self.page_text:
            frames = self.doc.d["stories"].get(self.page_text.sid, {}).get("frames", [])
            if not ids or any(i not in frames for i in ids):
                self.end_page_text()
        self.sel = list(ids); self.canvas.update()
        if self.tabs.currentIndex() != 0 and ids and self.tabs.currentIndex() != 3: self.tabs.setCurrentIndex(0)
        self.props.refresh()

    def select_all(self):
        if self.page_text:
            self.page_text.select_all(); self.canvas.update(); return
        if self.renderer.mode == "master":
            ids = [i["id"] for i in self.doc.d["items"] if i["on"].get("m") == self.renderer.master]
        else:
            p = self.renderer.pl(self.cur_page); keys = {q["key"] for q in self.renderer.placements if p and q["spread"] == p["spread"]}
            ids = [i["id"] for i in self.doc.d["items"] if i["on"].get("p") in keys]
        self.select(ids)

    def toggle_preview(self):
        self.preview = not self.preview; self.a_prev.setChecked(self.preview); self.canvas.update()

    def canvas_key(self, e):
        k, mod = e.key(), e.modifiers()
        if mod & (Qt.ControlModifier | Qt.MetaModifier): return False
        if k == Qt.Key_Escape:
            if self.link_from: self.cancel_link()
            else: self.select([]); self.set_tool("select")
            return True
        if k in (Qt.Key_Delete, Qt.Key_Backspace): self.delete_sel(); return True
        if k in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and self.sel:
            d = 5 if mod & Qt.ShiftModifier else 0.5
            if not e.isAutoRepeat(): self.commit()
            for i in self.sel:
                it = self.doc.item(i)
                if k == Qt.Key_Left: it["x"] = r2(it["x"] - d)
                if k == Qt.Key_Right: it["x"] = r2(it["x"] + d)
                if k == Qt.Key_Up: it["y"] = r2(it["y"] - d)
                if k == Qt.Key_Down: it["y"] = r2(it["y"] + d)
            self.canvas.update(); self.props.refresh_geometry(); return True
        tools = {Qt.Key_V: "select", Qt.Key_T: "text", Qt.Key_F: "image", Qt.Key_M: "rect", Qt.Key_L: "ellipse"}
        if k in tools: self.set_tool(tools[k]); return True
        if k == Qt.Key_W: self.toggle_preview(); return True
        if k in (Qt.Key_Plus, Qt.Key_Equal): self.set_zoom(self.canvas.zoom * 1.25); return True
        if k == Qt.Key_Minus: self.set_zoom(self.canvas.zoom / 1.25); return True
        return False

    # ------------------------------------------------------------ zoom / navigation
    def set_zoom(self, z, keep=True):
        sb, vb = self.scroll.horizontalScrollBar(), self.scroll.verticalScrollBar()
        old = self.canvas.zoom; vw, vh = self.scroll.viewport().width(), self.scroll.viewport().height()
        cx, cy = (sb.value() + vw / 2) / old, (vb.value() + vh / 2) / old
        self.canvas.zoom = clamp(z, 0.1, 8); self.canvas.resize_board()
        self.zoom_lbl.setText(f"{round(self.canvas.zoom * 100)} %")
        if keep:
            sb.setValue(int(cx * self.canvas.zoom - vw / 2)); vb.setValue(int(cy * self.canvas.zoom - vh / 2))

    def zoom_fit(self):
        d = self.doc.d
        W = (2 * d["w"] + 60 if d["facing"] else d["w"] + 60) * PX_MM; H = (d["h"] + 40) * PX_MM
        vp = self.scroll.viewport()
        self.set_zoom(min(vp.width() / W, vp.height() / H) * 0.98, False)
        self.scroll_to_page(self.cur_page)

    def scroll_to_page(self, key):
        p = self.renderer.pl(key) or (self.renderer.placements[0] if self.renderer.placements else None)
        if p: self.scroll.verticalScrollBar().setValue(int((p["y"] - 12) * self.canvas.S()))

    def set_current_page(self, pid):
        self.cur_page = pid; self.pages.refresh()

    def goto_page(self, pid):
        self.cur_page = pid
        if self.renderer.mode == "master": self.exit_master()
        else: self.pages.refresh(); self.scroll_to_page(pid)

    def goto_item(self, iid):
        it = self.doc.item(iid)
        if not it: return
        if "m" in it["on"] and (self.renderer.mode != "master" or self.renderer.master != it["on"]["m"]): self.enter_master(it["on"]["m"])
        if "p" in it["on"] and self.renderer.mode == "master": self.exit_master()
        if "p" in it["on"]: self.cur_page = it["on"]["p"]
        self.select([iid]); self.pages.refresh()
        b = self.canvas.item_box(it)
        if b:
            self.scroll.verticalScrollBar().setValue(int((b.y() - 20) * self.canvas.S()))
            self.scroll.horizontalScrollBar().setValue(int((b.x() - 20) * self.canvas.S()))

    # ------------------------------------------------------------ pages et gabarits
    def page_op(self, op):
        d = self.doc.d
        i = next((k for k, p in enumerate(d["pages"]) if p["id"] == self.cur_page), len(d["pages"]) - 1)
        self.commit()
        if op in ("add", "ins"):
            np_ = {"id": uid("p"), "m": d["masters"][0]["id"] if d["masters"] else ""}
            d["pages"].insert(len(d["pages"]) if op == "add" else i + 1, np_); self.cur_page = np_["id"]
        elif op == "del" and len(d["pages"]) > 1:
            pid = d["pages"][i]["id"]
            for it in [it for it in d["items"] if it["on"].get("p") == pid]:
                if it["type"] == "text": self.doc.remove_frame_from_story(it)
            d["items"] = [it for it in d["items"] if it["on"].get("p") != pid]
            d["pages"].pop(i); self.cur_page = d["pages"][min(i, len(d["pages"]) - 1)]["id"]; self.sel = []
        elif op == "up" and i > 0: d["pages"][i - 1], d["pages"][i] = d["pages"][i], d["pages"][i - 1]
        elif op == "down" and i < len(d["pages"]) - 1: d["pages"][i + 1], d["pages"][i] = d["pages"][i], d["pages"][i + 1]
        self.refresh()
        if op in ("add", "ins"): self.scroll_to_page(self.cur_page)

    def set_page_master(self, mid):
        self.commit(); next(p for p in self.doc.d["pages"] if p["id"] == self.cur_page)["m"] = mid; self.refresh()

    def add_master(self):
        self.commit(); used = [m["id"] for m in self.doc.d["masters"]]
        mid = next(c for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if c not in used)
        self.doc.d["masters"].append({"id": mid, "name": f"{mid}-Gabarit"}); self.enter_master(mid)

    def del_master(self):
        d = self.doc.d
        if len(d["masters"]) < 2: return
        self.commit(); mid = self.renderer.master
        d["masters"] = [m for m in d["masters"] if m["id"] != mid]
        for it in [i for i in d["items"] if i["on"].get("m") == mid]:
            if it["type"] == "text": d["stories"].pop(it["story"], None)
        d["items"] = [i for i in d["items"] if i["on"].get("m") != mid]
        for p in d["pages"]:
            if p.get("m") == mid: p["m"] = d["masters"][0]["id"]
        self.exit_master()

    def rename_master(self, name):
        m = next(m for m in self.doc.d["masters"] if m["id"] == self.renderer.master)
        if name and name != m["name"]: self.commit(); m["name"] = name; self.pages.refresh()

    def enter_master(self, mid):
        self.renderer.mode, self.renderer.master, self.sel = "master", mid, []
        self.refresh(); self.scroll.verticalScrollBar().setValue(0)
        self.msg(f"Tu modifies le gabarit {mid}. Clique sur « Retour aux pages » pour revenir.", 6000)

    def exit_master(self):
        self.renderer.mode, self.sel = "pages", []
        self.refresh(); self.scroll_to_page(self.cur_page)

    # ------------------------------------------------------------ blocs
    def create_item(self, kind, p, box):
        self.commit()
        it = {"id": uid("i"), "type": kind, "on": {"p": p["id"]} if p["kind"] == "page" else {"m": p["m"], "s": p["side"]},
              **box, "fill": None, "stroke": None, "sw": 0.5}
        if kind == "text":
            sid = uid("s"); self.doc.d["stories"][sid] = {"paras": [{"s": "corps", "h": ""}], "frames": [it["id"]]}
            it["story"], it["inset"] = sid, 0
        if kind == "image": it.update(asset=None, fit="cover", fx=50, fy=50)
        if kind in ("rect", "ellipse"): it["fill"] = "gris"
        self.doc.d["items"].append(it); self.sel = [it["id"]]
        self.set_tool("select"); self.refresh()
        if kind == "text": self.start_page_text(it["story"])
        if kind == "image": self.pick_image(it["id"], commit=False)
        return it

    def delete_sel(self):
        if not self.sel: return
        self.commit()
        for iid in self.sel:
            it = self.doc.item(iid)
            if not it: continue
            if it["type"] == "text":
                sid = it["story"]; self.doc.remove_frame_from_story(it)
                if sid not in self.doc.d["stories"] and self.editing == sid: self.close_editor(silent=True)
            self.doc.d["items"] = [i for i in self.doc.d["items"] if i["id"] != iid]
        self.sel = []; self.refresh()

    def duplicate(self):
        if not self.sel or self.page_text: return
        self.commit(); new = []
        for iid in self.sel:
            it = self.doc.item(iid); c = json.loads(json.dumps(it)); c["id"] = uid("i"); c["x"] += 5; c["y"] += 5
            if c["type"] == "text":
                st = self.doc.d["stories"][it["story"]]; sid = uid("s")
                self.doc.d["stories"][sid] = {"paras": json.loads(json.dumps(st["paras"] if len(st["frames"]) == 1 else [{"s": "corps", "h": ""}])), "frames": [c["id"]]}
                c["story"] = sid
            self.doc.d["items"].append(c); new.append(c["id"])
        self.sel = new; self.refresh()

    def z_order(self, direction):
        if not self.sel: return
        self.commit(); d = self.doc.d
        sel = [i for i in d["items"] if i["id"] in self.sel]; rest = [i for i in d["items"] if i["id"] not in self.sel]
        d["items"] = rest + sel if direction > 0 else sel + rest; self.refresh(reflow=False)

    def align_sel(self, k):
        its = [self.doc.item(i) for i in self.sel]; self.commit()
        L, R = min(i["x"] for i in its), max(i["x"] + i["w"] for i in its)
        T, B = min(i["y"] for i in its), max(i["y"] + i["h"] for i in its)
        for i in its:
            if k == "l": i["x"] = L
            if k == "r": i["x"] = r2(R - i["w"])
            if k == "c": i["x"] = r2((L + R) / 2 - i["w"] / 2)
            if k == "t": i["y"] = T
            if k == "b": i["y"] = r2(B - i["h"])
            if k == "m": i["y"] = r2((T + B) / 2 - i["h"] / 2)
        self.refresh()

    def set_prop(self, key, v, commit=True):
        if len(self.sel) != 1: return
        it = self.doc.item(self.sel[0])
        if it.get(key) == v: return
        if commit: self.commit(merge=f"prop:{it['id']}:{key}")
        it[key] = v
        if key in ("w", "h", "inset") and it["type"] == "text":
            if "m" in it["on"]: self.renderer.invalidate_masters()
            else: self.renderer.reflow({it["story"]})
        self.canvas.update()
        if key in ("fit", "inset", "w", "h", "fill", "stroke"):
            QTimer.singleShot(0, self.refresh_panels)

    # ------------------------------------------------------------ chaînage
    def start_link(self):
        self.link_from = self.sel[0]; self.canvas.setCursor(Qt.PointingHandCursor)
        self.msg("Clique sur un bloc texte (ou dans une page vide) pour y faire couler la suite. Échap pour annuler.", 8000)

    def cancel_link(self):
        self.link_from = None; self.canvas.setCursor(Qt.ArrowCursor); self.msg("")

    def finish_link(self, x, y, dst):
        src = self.doc.item(self.link_from); self.cancel_link()
        if not src: return
        d = self.doc.d
        if dst is None:
            p = self.canvas.pl_at(x, y)
            if not p or p["kind"] != "page": return
            self.commit()
            mg = self.doc.margins_for(p["side"])
            dx = r2(clamp(x - p["x"], 0, d["w"] - 10))
            if abs(dx - mg["l"]) < 10: dx = mg["l"]
            dst = {"id": uid("i"), "type": "text", "on": {"p": p["id"]}, "x": dx, "y": r2(clamp(y - p["y"], 0, d["h"] - 10)),
                   "w": src["w"], "h": src["h"], "fill": None, "stroke": None, "sw": .5, "inset": src.get("inset", 0), "story": None}
            d["items"].append(dst)
        else:
            if dst["type"] != "text" or "m" in dst["on"]:
                self.msg("Choisis un bloc texte sur une page"); return
            if dst["story"] == src["story"]:
                self.msg("Ce bloc fait déjà partie de ce texte"); return
            old = d["stories"][dst["story"]]
            if len(old["frames"]) > 1:
                self.msg("Ce bloc est déjà chaîné à un autre texte"); return
            self.commit()
            if any(re.sub(r"<[^>]+>", "", p["h"]).strip() for p in old["paras"]):
                d["stories"][src["story"]]["paras"] += old["paras"]
            del d["stories"][dst["story"]]
        st = d["stories"][src["story"]]
        st["frames"].insert(st["frames"].index(src["id"]) + 1, dst["id"]); dst["story"] = src["story"]
        self.sel = [dst["id"]]; self.refresh()
        if self.editing == src["story"]: self.editor.load(self.editing)

    def unlink_frame(self, iid):
        it = self.doc.item(iid); st = self.doc.d["stories"][it["story"]]
        if len(st["frames"]) < 2: return
        self.commit(); st["frames"].remove(iid)
        sid = uid("s"); self.doc.d["stories"][sid] = {"paras": [{"s": "corps", "h": ""}], "frames": [iid]}; it["story"] = sid
        self.refresh()

    # ------------------------------------------------------------ texte
    # ------------------------------------------------------------ texte sur la page
    def start_page_text(self, sid, at=None):
        if sid not in self.doc.d["stories"]: return
        if self.editing: self.close_editor()
        if self.page_text and self.page_text.sid != sid: self.end_page_text()
        if not self.page_text:
            self.page_text = PageText(self, sid)
            last = len(self.doc.d["stories"][sid]["paras"]) - 1
            self.page_text.caret = self.page_text.anchor = (last, self.page_text.plen(last))
        if at:
            pos = self.page_text.hit(*at)
            if pos is not None: self.page_text.caret = self.page_text.anchor = pos
        fr = self.doc.d["stories"][sid]["frames"]
        if not any(i in fr for i in self.sel): self.sel = [fr[0]]
        self.set_tool("select"); self.canvas.setFocus(); self.canvas.update()
        self.props.refresh(); self.msg("Saisie sur la page : tape ton texte. Échap pour terminer.", 5000)

    def end_page_text(self):
        if not self.page_text: return
        self.page_text.stop(); self.page_text = None
        self.canvas.update(); self.props.refresh()

    def page_text_changed(self, sid):
        st = self.doc.d["stories"].get(sid)
        if not st: return
        self.dirty = True; self.autosave_timer.start()
        first = self.doc.item(st["frames"][0]) if st["frames"] else None
        if first and "m" in first["on"]: self.renderer.invalidate_masters()
        else: self.renderer.reflow({sid})
        self.canvas.update()
        n = self.check.refresh(); self.tabs.setTabText(3, f"Contrôle ({n})" if n else "Contrôle")
        self.update_title(); self.page_text_caret()

    def page_text_caret(self):
        self.props.sync_text_tools()
        r = self.page_text.caret_rect_board() if self.page_text else None
        if r:
            S = self.canvas.S()
            self.scroll.ensureVisible(int(r.center().x() * S), int(r.center().y() * S), 60, 60)
        self.canvas.update()

    def open_editor(self, sid):
        if sid not in self.doc.d["stories"]: return
        self.end_page_text()
        if self.editing and self.editing != sid: self.close_editor()
        if self.editing != sid:
            self.commit(); self._edsnap = json.dumps(self.doc.d["stories"][sid]["paras"])
        self.editing = sid; self.ed_dock.show(); self.editor.load(sid)

    def close_editor(self, silent=False):
        if not self.editing: return
        sid = self.editing; self.editing = None
        if not silent and sid in self.doc.d["stories"] and json.dumps(self.doc.d["stories"][sid]["paras"]) == self._edsnap and self.undo_stack:
            self.undo_stack.pop(); self.update_title()
        self.editor.sid = None; self.ed_dock.hide(); self.canvas.setFocus()

    def story_changed(self, sid, paras):
        st = self.doc.d["stories"].get(sid)
        if not st: return
        st["paras"] = paras; self.dirty = True; self.autosave_timer.start()
        first = self.doc.item(st["frames"][0]) if st["frames"] else None
        if first and "m" in first["on"]: self.renderer.invalidate_masters()
        else: self.renderer.reflow({sid})
        self.canvas.update()
        n = self.check.refresh(); self.tabs.setTabText(3, f"Contrôle ({n})" if n else "Contrôle")
        self.update_title()

    def styles_changed(self):
        self.renderer.reflow(); self.renderer.invalidate_masters(); self.canvas.update()
        if self.editing: self.editor.refresh_styles()
        if self.page_text: self.props.refresh()
        n = self.check.refresh(); self.tabs.setTabText(3, f"Contrôle ({n})" if n else "Contrôle")

    # ------------------------------------------------------------ images et polices
    def import_image_file(self, path):
        img = QImage(path)
        if img.isNull():
            self.msg("Image illisible"); return None
        with open(path, "rb") as f: raw = f.read()
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg"): mime = "image/jpeg"
        elif ext == ".png": mime = "image/png"
        else:
            buf = QBuffer(); buf.open(QIODevice.WriteOnly); img.save(buf, "PNG"); raw = bytes(buf.data()); mime = "image/png"
        aid = uid("a")
        self.doc.assets[aid] = {"name": os.path.basename(path), "data": f"data:{mime};base64," + base64.b64encode(raw).decode(), "w": img.width(), "h": img.height()}
        return aid

    def pick_image(self, iid, commit=True):
        fn, _ = QFileDialog.getOpenFileName(self, "Choisir une image", "", "Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.gif *.webp)")
        if not fn: return
        aid = self.import_image_file(fn)
        if not aid: return
        if commit: self.commit()
        it = self.doc.item(iid); it["asset"] = aid; it.setdefault("fit", "cover"); it.setdefault("fx", 50); it.setdefault("fy", 50)
        self.sel = [iid]; self.refresh(reflow=False)

    def eff_ppi(self, it):
        a = self.doc.assets.get(it.get("asset"))
        if not a: return 0
        f = it.get("fit", "cover")
        s = max(it["w"] / a["w"], it["h"] / a["h"]) if f == "cover" else min(it["w"] / a["w"], it["h"] / a["h"])
        return round(25.4 / s)

    def fit_frame_to_image(self):
        it = self.doc.item(self.sel[0]) if self.sel else None
        a = it and self.doc.assets.get(it.get("asset"))
        if not a: return
        self.commit(); it["h"] = r2(it["w"] * a["h"] / a["w"]); it["fit"] = "cover"; self.refresh(reflow=False)

    def import_font(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Importer une police", "", "Polices (*.ttf *.otf *.woff)")
        if not fn: return
        with open(fn, "rb") as f: b64 = base64.b64encode(f.read()).decode()
        base = os.path.splitext(os.path.basename(fn))[0]
        cf = {"fam": base, "w": 700 if re.search(r"bold|black|heavy|semibold|demi", base, re.I) else 400,
              "it": bool(re.search(r"italic|oblique", base, re.I)), "b64": b64}
        fam = fonts.register_custom(cf)
        if not fam:
            QMessageBox.warning(self, "Police", "Cette police n’a pas pu être lue."); return
        cf["fam"] = fam; self.commit()
        self.doc.d["customFonts"] = [c for c in self.doc.d["customFonts"] if c["b64"] != b64] + [cf]
        self.styles.refresh(); self.msg(f"Police « {fam} » importée")

    # ------------------------------------------------------------ fichiers
    def drop_file(self, path, x, y, hit):
        low = path.lower()
        if low.endswith(".json"):
            if self.confirm_discard(): self.load_file(path)
            return
        if low.endswith(".txt") and hit and hit["type"] == "text":
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = [l.strip() for l in f.read().replace("\r", "").split("\n") if l.strip()]
            self.commit(); st = self.doc.d["stories"][hit["story"]]
            import html as _h
            new = [{"s": "corps", "h": _h.escape(l, quote=False)} for l in lines]
            st["paras"] = new if not any(p["h"].strip() for p in st["paras"]) else st["paras"] + new
            self.refresh(); return
        aid = self.import_image_file(path)
        if not aid: return
        self.commit()
        if hit and hit["type"] == "image":
            hit["asset"] = aid; self.sel = [hit["id"]]; self.refresh(reflow=False); return
        p = self.canvas.pl_at(x, y); a = self.doc.assets[aid]; d = self.doc.d
        w = max(20, min(d["w"] * 0.6, a["w"] / 300 * 25.4)); h = w * a["h"] / a["w"]
        it = {"id": uid("i"), "type": "image", "on": {"p": p["id"]} if p["kind"] == "page" else {"m": p["m"], "s": p["side"]},
              "x": r2(clamp(x - p["x"] - w / 2, -d["bleed"], d["w"])), "y": r2(clamp(y - p["y"] - h / 2, -d["bleed"], d["h"])),
              "w": r2(w), "h": r2(h), "fill": None, "stroke": None, "sw": .5, "asset": aid, "fit": "contain", "fx": 50, "fy": 50}
        d["items"].append(it); self.sel = [it["id"]]; self.refresh(reflow=False)

    def project_json(self):
        clean = json.loads(json.dumps(self.doc.d))
        for st in clean["stories"].values(): st.pop("_over", None)
        return json.dumps({"app": "magouille-met-en-page", "v": 1, "doc": clean, "assets": self.doc.used_assets()}, ensure_ascii=False)

    def save(self):
        if not self.path: return self.save_as()
        try:
            with open(self.path, "w", encoding="utf-8") as f: f.write(self.project_json())
        except OSError as e:
            QMessageBox.warning(self, "Enregistrer", f"Impossible d’enregistrer :\n{e}"); return False
        self.dirty = False; self.update_title(); self.msg("Projet enregistré : " + os.path.basename(self.path)); return True

    def save_as(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Enregistrer le projet", self.doc.d["name"] + ".json", "Projet (*.json)")
        if not fn: return False
        if not fn.lower().endswith(".json"): fn += ".json"
        self.path = fn; return self.save()

    def load_project(self, o, path=None):
        if self.editing: self.close_editor(silent=True)
        d = o["doc"]; d.setdefault("customFonts", [])
        for cf in d["customFonts"]:
            fam = fonts.register_custom(cf)
            if fam and fam != cf["fam"]:
                for s in d["styles"]:
                    if s["font"] == cf["fam"]: s["font"] = fam
                cf["fam"] = fam
        from .model import default_char_styles
        d.setdefault("charStyles", default_char_styles())
        self.doc.d, self.doc.assets = d, o.get("assets") or {}
        if self.page_text: self.page_text.stop(); self.page_text = None
        self.renderer.images = {}; self.renderer.mode = "pages"
        self.undo_stack, self.redo_stack = [], []
        self.sel, self.path, self.dirty = [], path, False
        self.cur_page = d["pages"][0]["id"]
        self.refresh(); QTimer.singleShot(0, self.zoom_fit)

    def load_file(self, path):
        try:
            with open(path, encoding="utf-8") as f: o = json.load(f)
            if "doc" not in o or "pages" not in o["doc"]: raise ValueError
        except Exception:
            QMessageBox.warning(self, "Ouvrir", "Ce fichier n’est pas un projet valide."); return
        self.load_project(o, path); self.msg("Projet ouvert : " + o["doc"]["name"])

    def confirm_discard(self):
        if not self.dirty: return True
        r = QMessageBox.question(self, APP_NAME, "Enregistrer les modifications du document en cours ?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save: return bool(self.save())
        return r == QMessageBox.Discard

    def open_dialog(self):
        if not self.confirm_discard(): return
        fn, _ = QFileDialog.getOpenFileName(self, "Ouvrir un projet", "", "Projet (*.json)")
        if fn: self.load_file(fn)

    def new_dialog(self):
        if not self.confirm_discard(): return
        dlg = SetupDialog(self)
        if dlg.exec():
            v = dlg.values(); self.load_project({"doc": new_doc(**v), "assets": {}}); self.dirty = True; self.update_title()

    def setup_dialog(self):
        dlg = SetupDialog(self, self.doc.d, is_new=False)
        if dlg.exec():
            v = dlg.values(); v.pop("pages"); self.commit(); self.doc.d.update(v); self.refresh(); self.zoom_fit()

    def export_dialog(self):
        dlg = ExportDialog(self, self.doc.d)
        if not dlg.exec(): return
        a, b, bleed, marks = dlg.values()
        fn, _ = QFileDialog.getSaveFileName(self, "Exporter en PDF", self.doc.d["name"] + ".pdf", "PDF (*.pdf)")
        if not fn: return
        if not fn.lower().endswith(".pdf"): fn += ".pdf"
        from .pdfexport import export_pdf
        pd = QProgressDialog("Export du PDF…", None, 0, b - a + 1, self); pd.setWindowModality(Qt.WindowModal); pd.setMinimumDuration(300)
        try:
            export_pdf(self, fn, a, b, bleed, marks, lambda i, n: (pd.setValue(i), QApplication.processEvents()))
        except Exception as e:
            pd.close(); QMessageBox.warning(self, "Export PDF", f"Erreur pendant l’export :\n{e}"); return
        pd.close(); self.refresh(); self.msg("PDF exporté : " + os.path.basename(fn), 6000)

    # ------------------------------------------------------------ sauvegarde auto
    @staticmethod
    def autosave_path():
        d = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
        os.makedirs(d, exist_ok=True); return os.path.join(d, "derniere-session.json")

    def autosave(self):
        try:
            with open(self.autosave_path(), "w", encoding="utf-8") as f: f.write(self.project_json())
        except OSError:
            pass

    def closeEvent(self, e):
        if self.editing: self.editor.close_editor()
        if not self.confirm_discard(): e.ignore(); return
        self.autosave(); e.accept()

    def welcome(self):
        saved = None
        try:
            with open(self.autosave_path(), encoding="utf-8") as f: saved = json.load(f)
        except Exception:
            pass
        dlg = Welcome(self, saved["doc"]["name"] if saved else None)
        dlg.exec()
        c = dlg.choice
        if c == "new":
            s = SetupDialog(self)
            if s.exec(): v = s.values(); self.load_project({"doc": new_doc(**v), "assets": {}})
            else: return self.welcome()
        elif c == "example": self.load_project({"doc": example_doc(), "assets": {}})
        elif c == "open":
            fn, _ = QFileDialog.getOpenFileName(self, "Ouvrir un projet", "", "Projet (*.json)")
            if fn: self.load_file(fn)
            else: return self.welcome()
        elif c == "resume" and saved: self.load_project(saved); self.dirty = True; self.update_title()
        elif c == "help": HelpDialog(self).exec(); return self.welcome()
        else: QTimer.singleShot(0, self.zoom_fit)


QSS = """
QMainWindow, QDockWidget, QTabWidget::pane, QScrollArea > QWidget > QWidget { background:#fbfaf7; }
QDockWidget::title { padding:4px 8px; color:#7a766e; }
QToolBar { background:#ffffff; border-bottom:1px solid #dcd9d2; spacing:4px; padding:3px; }
QToolBar QToolButton { padding:3px 8px; border-radius:5px; }
QToolBar QToolButton:checked { background:#dfe6fb; border:1px solid #3a6ff0; }
QToolBar QToolButton:hover { background:#eeece6; }
QPushButton { background:#fff; border:1px solid #dcd9d2; border-radius:5px; padding:4px 10px; }
QPushButton:hover { border-color:#b9b4aa; }
QPushButton[primary="true"] { background:#d2462e; color:white; border-color:#d2462e; }
QTabBar::tab { padding:6px 10px; color:#7a766e; border:0; border-bottom:2px solid transparent; background:transparent; }
QTabBar::tab:selected { color:#222; border-bottom:2px solid #d2462e; }
QListWidget { background:#fff; border:1px solid #dcd9d2; border-radius:4px; }
QStatusBar { background:#fff; color:#7a766e; }
"""


def main():
    if sys.platform == "win32":
        # sans ça, Windows regroupe la fenêtre sous l'icône de Python dans la barre des tâches
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Magouille.MetEnPage.1")
        except Exception:
            pass
    QApplication.setApplicationName("Magouille met en page")
    QApplication.setOrganizationName("Magouille")
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = app.palette()
    for role, col in [(QPalette.Window, "#fbfaf7"), (QPalette.Base, "#ffffff"), (QPalette.Button, "#ffffff"), (QPalette.Text, "#222222"),
                      (QPalette.WindowText, "#222222"), (QPalette.ButtonText, "#222222"), (QPalette.Highlight, "#3a6ff0")]:
        pal.setColor(role, QColor(col))
    app.setPalette(pal); app.setStyleSheet(QSS); app.setWindowIcon(app_icon())
    fonts.load_builtin()
    w = MainWindow(); w.show()
    args = [a for a in sys.argv[1:] if a.lower().endswith(".json") and os.path.exists(a)]
    if args: w.load_file(args[0])
    else: QTimer.singleShot(50, w.welcome)
    sys.exit(app.exec())
