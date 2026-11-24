"""Table de montage : affichage des pages et interactions à la souris."""
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QFont, QCursor, QPolygonF, QTransform
import math
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from .model import MM, placement_key, r2, uid
from .render import item_xf, item_bounds

PX_MM = 96 / 25.4
C_MARGIN, C_COL, C_BLEED, C_SEL = QColor(212, 60, 196), QColor(138, 92, 240), QColor(227, 51, 51), QColor(58, 111, 240)
HANDLES = [(0, 0), (.5, 0), (1, 0), (1, .5), (1, 1), (.5, 1), (0, 1), (0, .5)]
CURSORS = {(0, 0): Qt.SizeFDiagCursor, (1, 1): Qt.SizeFDiagCursor, (1, 0): Qt.SizeBDiagCursor, (0, 1): Qt.SizeBDiagCursor,
           (.5, 0): Qt.SizeVerCursor, (.5, 1): Qt.SizeVerCursor, (0, .5): Qt.SizeHorCursor, (1, .5): Qt.SizeHorCursor}


def clamp(v, a, b):
    return max(a, min(b, v))


class Canvas(QWidget):
    posChanged = Signal(str)

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.zoom = 1.0
        self.drag = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)

    # ---------- raccourcis ----------
    @property
    def R(self): return self.win.renderer
    @property
    def D(self): return self.win.doc

    def S(self):  # px par mm
        return self.zoom * PX_MM

    def resize_board(self):
        W, H = self.R.board_size()
        self.setFixedSize(int(W * self.S()) + 1, int(H * self.S()) + 1)
        self.update()

    def to_mm(self, pos):
        return pos.x() / self.S(), pos.y() / self.S()

    def pl_at(self, x, y, loose=True):
        d = self.D.d
        best, bd = None, 1e9
        for p in self.R.placements:
            if p["x"] <= x <= p["x"] + d["w"] and p["y"] <= y <= p["y"] + d["h"]:
                return p
            dx = max(p["x"] - x, 0, x - p["x"] - d["w"]); dy = max(p["y"] - y, 0, y - p["y"] - d["h"])
            dd = (dx * dx + dy * dy) ** .5
            if dd < bd:
                bd, best = dd, p
        return best if loose else None

    def item_box(self, it):
        """Rectangle englobant sur la table (mm)."""
        p = self.R.pl(placement_key(it))
        if not p:
            return None
        return item_bounds(it).translated(p["x"], p["y"])

    def xf(self, it):
        """Repère du bloc (mm) -> table (mm)."""
        p = self.R.pl(placement_key(it))
        return item_xf(it, p["x"], p["y"], 1) if p else None

    def local(self, it, x, y):
        t = self.xf(it)
        if t is None: return None
        inv, _ = t.inverted(); q = inv.map(QPointF(x, y)); return q.x(), q.y()

    def item_at(self, x, y):
        for it in reversed(self.D.d["items"]):
            l = self.local(it, x, y)
            if l and -.5 <= l[0] <= it["w"] + .5 and -.5 <= l[1] <= it["h"] + .5:
                return it
        return None

    # ---------- dessin ----------
    def paintEvent(self, ev):
        win, d = self.win, self.D.d
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing); qp.setRenderHint(QPainter.TextAntialiasing); qp.setRenderHint(QPainter.SmoothPixmapTransform)
        qp.fillRect(ev.rect(), QColor(236, 235, 231))
        k = self.S() / MM  # px par point
        qp.scale(k, k)
        hair = 1 / k
        exposed = QRectF(ev.rect().x() / k, ev.rect().y() / k, ev.rect().width() / k, ev.rect().height() / k)
        w, h, bl = d["w"] * MM, d["h"] * MM, d["bleed"] * MM
        preview = win.preview
        f = QFont("Sans Serif"); f.setPointSizeF(8 / k * 0.75 * 1.33); qp.setFont(f)
        for p in self.R.placements:
            ox, oy = p["x"] * MM, p["y"] * MM
            if not QRectF(ox - 40, oy - 40, w + 80, h + 80).intersects(exposed):
                continue
            # ombre + page
            qp.fillRect(QRectF(ox + hair, oy + 2 * hair, w, h), QColor(0, 0, 0, 40))
            qp.fillRect(QRectF(ox, oy, w, h), Qt.white)
            qp.save()
            if preview:
                qp.setClipRect(QRectF(ox, oy, w, h))
            pt = self.win.page_text
            for it, fm in self.R.items_for(p):
                extra = pt.paint_extra(it) if (pt and not fm and it.get("story") == pt.sid) else None
                self.R.draw_item(qp, it, ox, oy, p, fm, screen=not preview, extra=extra)
            qp.restore()
            if preview:
                continue
            # repères
            mg = self.D.margins_for(p["side"])
            qp.setBrush(Qt.NoBrush)
            qp.setPen(QPen(C_MARGIN, hair))
            qp.drawRect(QRectF(ox + mg["l"] * MM, oy + mg["t"] * MM, w - (mg["l"] + mg["r"]) * MM, h - (mg["t"] + mg["b"]) * MM))
            if d["cols"] > 1:
                cw = (d["w"] - mg["l"] - mg["r"] - d["gutter"] * (d["cols"] - 1)) / d["cols"]
                qp.setPen(QPen(C_COL, hair))
                for c in range(1, d["cols"]):
                    for xx in (mg["l"] + c * cw + (c - 1) * d["gutter"], mg["l"] + c * cw + c * d["gutter"]):
                        qp.drawLine(QPointF(ox + xx * MM, oy + mg["t"] * MM), QPointF(ox + xx * MM, oy + h - mg["b"] * MM))
            if bl > 0:
                l = 0 if (d["facing"] and p["side"] == "R" and not p["alone"]) else bl
                r = 0 if (d["facing"] and p["side"] == "L") else bl
                qp.setPen(QPen(QColor(227, 51, 51, 150), hair))
                qp.drawRect(QRectF(ox - l, oy - bl, w + l + r, h + 2 * bl))
            # contours des blocs
            for it, fm in self.R.items_for(p):
                pen = QPen(QColor(0, 0, 0, 40) if fm else QColor(58, 111, 240, 80), hair)
                if fm: pen.setStyle(Qt.DashLine)
                qp.setPen(pen)
                qp.save(); qp.setTransform(item_xf(it, ox, oy), True)
                b = QRectF(0, 0, it["w"] * MM, it["h"] * MM)
                qp.drawRect(b)
                if it["type"] == "text" and not fm:
                    st = d["stories"].get(it.get("story"))
                    if st and st.get("_over") and st["frames"] and st["frames"][-1] == it["id"]:
                        s = 9 * hair
                        qp.fillRect(QRectF(b.right() - s, b.bottom() - s, s, s), C_BLEED)
                        qp.setPen(QPen(Qt.white, 1.5 * hair))
                        c = QPointF(b.right() - s / 2, b.bottom() - s / 2)
                        qp.drawLine(c - QPointF(s / 3, 0), c + QPointF(s / 3, 0)); qp.drawLine(c - QPointF(0, s / 3), c + QPointF(0, s / 3))
                qp.restore()
            # étiquette
            qp.setPen(QColor(122, 118, 110))
            label = (f"{p['num']}" + (f" · {p['m']}" if p.get("m") else "")) if p["kind"] == "page" else ("Gauche" if p["side"] == "L" else "Droite") if d["facing"] else f"Gabarit {p['m']}"
            qp.drawText(QRectF(ox, oy + h + 4 * MM / 1, w, 14 * hair), Qt.AlignHCenter | Qt.AlignTop, label)
        if not preview:
            self.paint_overlay(qp, hair)
        qp.end()

    def handle_pts(self, it):
        """Poignées (mm, table) : redimensionnement + rotation."""
        t = self.xf(it)
        pts = {(hx, hy): t.map(QPointF(it["w"] * hx, it["h"] * hy)) for hx, hy in HANDLES}
        pts["rot"] = t.map(QPointF(it["w"] / 2, -18 / self.S()))
        return pts

    def paint_overlay(self, qp, hair):
        win, d = self.win, self.D.d
        sel = [self.D.item(i) for i in win.sel if self.D.item(i)]
        qp.setBrush(Qt.NoBrush)
        editing = win.page_text is not None
        for it in sel:
            t = self.xf(it)
            if t is None: continue
            poly = QPolygonF([t.map(QPointF(a, b)) * MM for a, b in ((0, 0), (it["w"], 0), (it["w"], it["h"]), (0, it["h"]))])
            qp.setPen(QPen(C_SEL, hair)); qp.drawPolygon(poly)
            if len(sel) == 1 and not editing:
                hs = 7 * hair
                pts = self.handle_pts(it)
                top = pts[(.5, 0)] * MM; rp = pts["rot"] * MM
                qp.drawLine(top, rp)
                qp.setBrush(Qt.white); qp.drawEllipse(rp, hs * .7, hs * .7); qp.setBrush(Qt.NoBrush)
                for hx, hy in HANDLES:
                    c = pts[(hx, hy)] * MM
                    qp.fillRect(QRectF(c.x() - hs / 2, c.y() - hs / 2, hs, hs), Qt.white)
                    qp.drawRect(QRectF(c.x() - hs / 2, c.y() - hs / 2, hs, hs))
            if len(sel) == 1 and it["type"] == "text" and "p" in it["on"]:
                st = d["stories"][it["story"]]
                for prt, rr in self.ports(it).items():
                    last = st["frames"][-1] == it["id"]
                    over = prt == "out" and last and st.get("_over")
                    qp.fillRect(rr, C_BLEED if over else Qt.white)
                    qp.setPen(QPen(C_BLEED if over else C_SEL, hair)); qp.drawRect(rr)
                    mark = "+" if over else ("▸" if (prt == "out" and not last) or (prt == "in" and st["frames"][0] != it["id"]) else "")
                    if mark:
                        qp.setPen(Qt.white if over else C_SEL)
                        f = qp.font(); f.setPointSizeF(9 * hair); qp.setFont(f)
                        qp.drawText(rr, Qt.AlignCenter, mark)
                qp.setPen(QPen(C_SEL, hair))
                frs = [self.D.item(f) for f in st["frames"] if self.D.item(f)]
                for a, c in zip(frs, frs[1:]):
                    pa, pc = self.xf(a), self.xf(c)
                    if pa and pc:
                        qp.drawLine(pa.map(QPointF(a["w"] - 3, a["h"] - 2)) * MM, pc.map(QPointF(3, 2)) * MM)
        if self.drag and self.drag["kind"] == "create" and "cur" in self.drag:
            (x1, y1), (x2, y2) = self.drag["start"], self.drag["cur"]
            pen = QPen(C_SEL, hair); pen.setStyle(Qt.DashLine); qp.setPen(pen)
            qp.drawRect(QRectF(min(x1, x2) * MM, min(y1, y2) * MM, abs(x2 - x1) * MM, abs(y2 - y1) * MM))
        if self.drag and self.drag["kind"] == "rotate":
            it = self.D.item(self.drag["id"])
            qp.setPen(C_SEL); f = qp.font(); f.setPointSizeF(10 * hair); qp.setFont(f)
            c = self.drag["center"]
            qp.drawText(QPointF(c[0] * MM + 10 * hair, c[1] * MM - 10 * hair), f"{it.get('rot', 0):.1f}°")

    def ports(self, it):
        t = self.xf(it)
        s = 11 / (self.S() / MM)  # en points
        a = t.map(QPointF(3, 2)) * MM; b = t.map(QPointF(it["w"] - 3, it["h"] - 2)) * MM
        return {"in": QRectF(a.x() - s / 2, a.y() - s / 2, s, s), "out": QRectF(b.x() - s / 2, b.y() - s / 2, s, s)}

    def handle_at(self, x, y):
        if len(self.win.sel) != 1 or self.win.page_text: return None
        it = self.D.item(self.win.sel[0])
        if not it or not self.xf(it): return None
        tol = 6 / self.S()
        for k, pt in self.handle_pts(it).items():
            if abs(x - pt.x()) <= tol and abs(y - pt.y()) <= tol:
                return k
        return None

    def port_at(self, x, y):
        if len(self.win.sel) != 1: return None
        it = self.D.item(self.win.sel[0])
        if not it or it["type"] != "text" or "p" not in it["on"]: return None
        for k, r in self.ports(it).items():
            if r.adjusted(-2, -2, 2, 2).contains(QPointF(x * MM, y * MM)):
                return k
        return None

    # ---------- magnétisme ----------
    def snap_targets(self, p, excl):
        d = self.D.d; mg = self.D.margins_for(p["side"])
        xs = [0, d["w"], d["w"] / 2, mg["l"], d["w"] - mg["r"]]; ys = [0, d["h"], d["h"] / 2, mg["t"], d["h"] - mg["b"]]
        if d["cols"] > 1:
            cw = (d["w"] - mg["l"] - mg["r"] - d["gutter"] * (d["cols"] - 1)) / d["cols"]
            for c in range(1, d["cols"]):
                xs += [mg["l"] + c * cw + (c - 1) * d["gutter"], mg["l"] + c * cw + c * d["gutter"]]
        for it in d["items"]:
            if it["id"] not in excl and placement_key(it) == p["key"]:
                bb = item_bounds(it)
                xs += [bb.left(), bb.right(), bb.center().x()]; ys += [bb.top(), bb.bottom(), bb.center().y()]
        return xs, ys

    @staticmethod
    def snap(vals, targets, th):
        best = None
        for v in vals:
            for t in targets:
                dd = t - v
                if abs(dd) <= th and (best is None or abs(dd) < abs(best)):
                    best = dd
        return best or 0

    # ---------- souris ----------
    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() != Qt.LeftButton:
            return
        win = self.win
        x, y = self.to_mm(e.position())
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        # saisie sur la page : clic dans le texte en cours
        pt = win.page_text
        if pt:
            pos = pt.hit(x, y)
            if pos is not None:
                pt.move(pos, shift); self.drag = dict(kind="textsel"); self.update(); return
            win.end_page_text()
        if win.link_from:
            win.finish_link(x, y, self.item_at(x, y)); return
        port = self.port_at(x, y)
        if port == "out":
            win.start_link(); return
        hnd = self.handle_at(x, y)
        if hnd:
            it = self.D.item(win.sel[0])
            if hnd == "rot":
                c = self.xf(it).map(QPointF(it["w"] / 2, it["h"] / 2))
                self.drag = dict(kind="rotate", id=it["id"], center=(c.x(), c.y()), orig=dict(it), moved=False, start=(x, y)); return
            self.drag = dict(kind="resize", id=it["id"], hx=hnd[0], hy=hnd[1], start=(x, y), orig=dict(it), moved=False); return
        hit = self.item_at(x, y)
        if hit is not None and win.renderer.mode == "pages" and "m" in hit["on"]:
            hit = None
        tool = win.tool
        if tool == "select" or (tool == "text" and hit and hit["type"] == "text"):
            if tool == "text" and hit:
                win.select([hit["id"]]); win.start_page_text(hit["story"], (x, y)); self.drag = dict(kind="textsel"); return
            if hit:
                if shift:
                    win.select([i for i in win.sel if i != hit["id"]] if hit["id"] in win.sel else win.sel + [hit["id"]]); return
                if hit["id"] not in win.sel:
                    win.select([hit["id"]])
                self.drag = dict(kind="move", start=(x, y), origs=[dict(self.D.item(i)) for i in win.sel], moved=False)
            else:
                win.select([])
                p = self.pl_at(x, y, False)
                if p and p["kind"] == "page":
                    win.set_current_page(p["id"])
            return
        p = self.pl_at(x, y)
        if p:
            self.drag = dict(kind="create", pl=p, start=(x, y), cur=(x, y), moved=False)

    def mouseMoveEvent(self, e):
        x, y = self.to_mm(e.position())
        p = self.pl_at(x, y, False)
        self.posChanged.emit(f"x {x - p['x']:.1f} mm · y {y - p['y']:.1f} mm" if p else "")
        win = self.win
        if not self.drag:
            hnd = self.handle_at(x, y)
            if win.link_from: self.setCursor(Qt.PointingHandCursor)
            elif hnd == "rot": self.setCursor(Qt.CrossCursor)
            elif hnd:
                it = self.D.item(win.sel[0])
                self.setCursor(CURSORS[hnd] if not it.get("rot") else Qt.SizeAllCursor)
            elif self.port_at(x, y): self.setCursor(Qt.PointingHandCursor)
            elif win.page_text and win.page_text.hit(x, y) is not None: self.setCursor(Qt.IBeamCursor)
            elif win.tool == "text": self.setCursor(Qt.IBeamCursor)
            elif win.tool in ("image", "rect", "ellipse"): self.setCursor(Qt.CrossCursor)
            else: self.setCursor(Qt.ArrowCursor)
            return
        dr = self.drag
        if dr["kind"] == "textsel":
            pt = win.page_text
            if pt:
                pos = pt.hit(x, y)
                if pos is not None: pt.caret = pos; pt.poke(); self.update()
            return
        dx, dy = x - dr["start"][0], y - dr["start"][1]
        if (dx * dx + dy * dy) ** .5 * self.S() > 2:
            dr["moved"] = True
        if not dr["moved"]:
            return
        th = 6 / self.S()
        snap = not (e.modifiers() & Qt.AltModifier)
        shift = bool(e.modifiers() & Qt.ShiftModifier)
        if dr["kind"] == "move":
            lead = dr["origs"][0]; pl = self.R.pl(placement_key(lead))
            sx = sy = 0
            if snap and pl:
                xs, ys = self.snap_targets(pl, win.sel)
                bb = item_bounds(lead).translated(dx, dy)
                sx = self.snap([bb.left(), bb.right(), bb.center().x()], xs, th)
                sy = self.snap([bb.top(), bb.bottom(), bb.center().y()], ys, th)
            if shift:
                if abs(dx) > abs(dy): sy = -dy
                else: sx = -dx
            for o in dr["origs"]:
                it = self.D.item(o["id"]); it["x"] = r2(o["x"] + dx + sx); it["y"] = r2(o["y"] + dy + sy)
            win.props_refresh_geometry()
        elif dr["kind"] == "rotate":
            it = self.D.item(dr["id"]); cx, cy = dr["center"]
            ang = math.degrees(math.atan2(y - cy, x - cx)) + 90
            if shift: ang = round(ang / 15) * 15
            else:
                for k in (0, 90, 180, 270, 360, -90, -180):
                    if abs(ang - k) < 2: ang = k
            ang = (ang + 180) % 360 - 180
            it["rot"] = round(ang, 1)
            win.props_refresh_geometry()
        elif dr["kind"] == "resize":
            o, it = dr["orig"], self.D.item(dr["id"])
            rot = o.get("rot", 0) or 0
            pl = self.R.pl(placement_key(it))
            if not rot:
                xs, ys = self.snap_targets(pl, [it["id"]]) if snap and pl else ([], [])
                sn = lambda v, arr: v + self.snap([v], arr, th)
                x1, y1, x2, y2 = o["x"], o["y"], o["x"] + o["w"], o["y"] + o["h"]
                if dr["hx"] == 0: x1 = sn(o["x"] + dx, xs)
                if dr["hx"] == 1: x2 = sn(o["x"] + o["w"] + dx, xs)
                if dr["hy"] == 0: y1 = sn(o["y"] + dy, ys)
                if dr["hy"] == 1: y2 = sn(o["y"] + o["h"] + dy, ys)
                if shift and dr["hx"] != .5 and dr["hy"] != .5:
                    hh = abs(x2 - x1) * o["h"] / o["w"]
                    if dr["hy"] == 0: y1 = y2 - hh
                    else: y2 = y1 + hh
                it["x"], it["y"] = r2(min(x1, x2)), r2(min(y1, y2))
                it["w"], it["h"] = r2(max(1, abs(x2 - x1))), r2(max(1, abs(y2 - y1)))
            else:
                # bloc tourné : on travaille dans le repère du bloc, le côté opposé reste en place
                a = math.radians(rot); ca, sa = math.cos(a), math.sin(a)
                ldx, ldy = dx * ca + dy * sa, -dx * sa + dy * ca
                x1, x2, y1, y2 = -o["w"] / 2, o["w"] / 2, -o["h"] / 2, o["h"] / 2
                if dr["hx"] == 0: x1 += ldx
                if dr["hx"] == 1: x2 += ldx
                if dr["hy"] == 0: y1 += ldy
                if dr["hy"] == 1: y2 += ldy
                if shift and dr["hx"] != .5 and dr["hy"] != .5:
                    hh = abs(x2 - x1) * o["h"] / o["w"]
                    if dr["hy"] == 0: y1 = y2 - hh
                    else: y2 = y1 + hh
                w, h = max(1, abs(x2 - x1)), max(1, abs(y2 - y1))
                lcx, lcy = (x1 + x2) / 2, (y1 + y2) / 2
                ocx, ocy = o["x"] + o["w"] / 2, o["y"] + o["h"] / 2
                ncx, ncy = ocx + lcx * ca - lcy * sa, ocy + lcx * sa + lcy * ca
                it["w"], it["h"] = r2(w), r2(h); it["x"], it["y"] = r2(ncx - w / 2), r2(ncy - h / 2)
            if it["type"] == "text":
                if "m" in it["on"]: self.R.invalidate_masters()
                else: self.R.reflow({it["story"]})
            win.props_refresh_geometry()
        elif dr["kind"] == "create":
            dr["cur"] = (x, y)
        self.update()

    def mouseReleaseEvent(self, e):
        dr, self.drag = self.drag, None
        if not dr:
            return
        win = self.win
        if dr["kind"] == "textsel":
            win.page_text_caret(); return
        if dr["kind"] == "move" and dr["moved"]:
            for o in dr["origs"]:  # changement de page si lâché ailleurs
                it = self.D.item(o["id"]); pl = self.R.pl(placement_key(it))
                if not pl: continue
                cx, cy = pl["x"] + it["x"] + it["w"] / 2, pl["y"] + it["y"] + it["h"] / 2
                np_ = self.pl_at(cx, cy, False)
                if np_ and np_["key"] != pl["key"] and np_["kind"] == pl["kind"]:
                    it["x"] = r2(it["x"] + pl["x"] - np_["x"]); it["y"] = r2(it["y"] + pl["y"] - np_["y"])
                    it["on"] = {"p": np_["id"]} if np_["kind"] == "page" else {"m": np_["m"], "s": np_["side"]}
            win.commit_before(dr["origs"]); win.refresh(reflow=True)
        elif dr["kind"] in ("resize", "rotate") and dr["moved"]:
            win.commit_before([dr["orig"]]); win.refresh(reflow=True)
        elif dr["kind"] == "create":
            p = dr["pl"]; (x1, y1), (x2, y2) = dr["start"], dr["cur"]
            x, y, w, h = min(x1, x2) - p["x"], min(y1, y2) - p["y"], abs(x2 - x1), abs(y2 - y1)
            if w < 3 or h < 3:
                mg = self.D.margins_for(p["side"])
                w = self.D.d["w"] - mg["l"] - mg["r"] if win.tool == "text" else 50
                h = 40
                x, y = clamp(x, 0, self.D.d["w"] - w), clamp(y, 0, self.D.d["h"] - h)
            win.create_item(win.tool, p, dict(x=r2(x), y=r2(y), w=r2(w), h=r2(h)))
        self.update()

    def mouseDoubleClickEvent(self, e):
        x, y = self.to_mm(e.position())
        win = self.win
        if win.page_text:
            pos = win.page_text.hit(x, y)
            if pos is not None:
                win.page_text.select_word(pos); self.update(); return
        it = self.item_at(x, y)
        if not it or (win.renderer.mode == "pages" and "m" in it["on"]):
            return
        if it["type"] == "text": win.start_page_text(it["story"], (x, y))
        elif it["type"] == "image": win.pick_image(it["id"])

    def wheelEvent(self, e):
        if e.modifiers() & Qt.ControlModifier:
            self.win.set_zoom(self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1))
            e.accept()
        else:
            e.ignore()

    # ---------- glisser-déposer de fichiers ----------
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if not urls: return
        x, y = self.to_mm(e.position())
        self.win.drop_file(urls[0], x, y, self.item_at(x, y))
        e.acceptProposedAction()

    # ---------- clavier et méthodes de saisie (accents, etc.) ----------
    def keyPressEvent(self, e):
        if self.win.page_text and self.win.page_text.key(e):
            self.update(); return
        if not self.win.canvas_key(e):
            super().keyPressEvent(e)

    def focusNextPrevChild(self, nxt):
        return False if self.win.page_text else super().focusNextPrevChild(nxt)

    def inputMethodEvent(self, e):
        if self.win.page_text and e.commitString():
            self.win.page_text.insert(e.commitString()); self.update()
        e.accept()

    def inputMethodQuery(self, q):
        if q == Qt.ImEnabled:
            return self.win.page_text is not None
        if q == Qt.ImCursorRectangle and self.win.page_text:
            r = self.win.page_text.caret_rect_board()
            if r: return QRectF(r.x() * self.S(), r.y() * self.S(), max(1, r.width() * self.S()), r.height() * self.S()).toRect()
        return super().inputMethodQuery(q)
