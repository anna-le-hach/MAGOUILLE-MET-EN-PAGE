"""Dessin des pages : le même code sert à l'écran et à l'export PDF (unités : points)."""
import base64
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QImage, QPainterPath, QTransform
from PySide6.QtCore import Qt, QRectF, QPointF
from .model import MM, placement_key
from .textflow import flow_story, swatch_qcolor

GAP = 22  # mm entre les planches


def item_xf(it, ox=0.0, oy=0.0, unit=MM):
    """Transformation repère du bloc -> repère de la page (rotation autour du centre).
    unit = MM pour travailler en points, 1 pour travailler en millimètres."""
    w, h = it["w"] * unit, it["h"] * unit
    t = QTransform()
    t.translate(ox + it["x"] * unit + w / 2, oy + it["y"] * unit + h / 2)
    t.rotate(it.get("rot", 0) or 0)
    t.translate(-w / 2, -h / 2)
    return t


def item_bounds(it):
    """Rectangle englobant (mm, repère de la page) d'un bloc, rotation comprise."""
    if not it.get("rot"):
        return QRectF(it["x"], it["y"], it["w"], it["h"])
    return item_xf(it, 0, 0, 1).mapRect(QRectF(0, 0, it["w"], it["h"]))


class Renderer:
    def __init__(self, doc):
        self.doc = doc
        self.flows = {}        # story id -> Flow
        self.master_flows = {} # (story id, n) -> Flow
        self.images = {}       # asset id -> QImage
        self.placements = []
        self.mode, self.master = "pages", None

    # ---------- placement des pages sur la table de montage (mm) ----------
    def layout(self):
        d, D = self.doc.d, self.doc
        out, w, h = [], d["w"], d["h"]
        spine = 30 + w
        if self.mode == "master":
            sides = ["L", "R"] if d["facing"] else ["R"]
            for s in sides:
                out.append(dict(key=f"M:{self.master}:{s}", kind="master", m=self.master, side=s,
                                x=(spine - w if s == "L" else spine) if d["facing"] else 30, y=20, num=self.master, spread=0, alone=not d["facing"]))
        else:
            y = 20
            for si, grp in enumerate(D.spreads()):
                for k in grp:
                    side = D.page_side(k)
                    pg = d["pages"][k]
                    out.append(dict(key=pg["id"], kind="page", id=pg["id"], idx=k, m=pg.get("m") or "", side=side,
                                    x=(spine - w if side == "L" else spine) if d["facing"] else 30, y=y, num=k + 1, spread=si, alone=len(grp) == 1))
                y += h + GAP
        self.placements = out
        return out

    def board_size(self):
        d = self.doc.d
        W = 60 + (2 * d["w"] if d["facing"] else d["w"])
        H = max([p["y"] + d["h"] for p in self.placements] + [100]) + 30
        return W, H

    def pl(self, key):
        for p in self.placements:
            if p["key"] == key:
                return p
        return None

    # ---------- composition ----------
    def reflow(self, only=None):
        d, D = self.doc.d, self.doc
        total = len(d["pages"])
        page_num = {p["id"]: i + 1 for i, p in enumerate(d["pages"])}
        for sid, st in list(d["stories"].items()):
            if only and sid not in only:
                continue
            first = D.item(st["frames"][0]) if st["frames"] else None
            if first and "m" in first["on"]:
                self.master_flows = {k: v for k, v in self.master_flows.items() if k[0] != sid}
                continue
            frames = []
            for fid in st["frames"]:
                it = D.item(fid)
                if not it:
                    continue
                ins = (it.get("inset") or 0) * 2
                frames.append((fid, max(1, (it["w"] - ins) * MM), max(1, (it["h"] - ins) * MM), page_num.get(it["on"].get("p"), 1)))
            self.flows[sid] = flow_story(D, st["paras"], frames, total)
            st["_over"] = self.flows[sid].overset

    def master_flow(self, it, n):
        st = self.doc.d["stories"].get(it["story"])
        if not st:
            return None
        key = (it["story"], str(n), it["w"], it["h"], it.get("inset"))
        if key not in self.master_flows:
            ins = (it.get("inset") or 0) * 2
            self.master_flows[key] = flow_story(self.doc, st["paras"], [(it["id"], max(1, (it["w"] - ins) * MM), max(1, (it["h"] - ins) * MM), n)], len(self.doc.d["pages"]))
        return self.master_flows[key]

    def invalidate_masters(self):
        self.master_flows = {}

    # ---------- images ----------
    def qimage(self, aid):
        if aid not in self.images:
            a = self.doc.assets.get(aid)
            img = QImage()
            if a:
                data = a["data"].split(",", 1)[1] if a["data"].startswith("data:") else a["data"]
                img.loadFromData(base64.b64decode(data))
            self.images[aid] = img
        return self.images[aid]

    # ---------- dessin ----------
    def items_for(self, p):
        """(item, est_gabarit) dessinés sur une page, dans l'ordre."""
        d = self.doc.d
        out = []
        if p["kind"] == "page" and p["m"]:
            out += [(it, True) for it in d["items"] if it["on"].get("m") == p["m"] and it["on"].get("s") == p["side"]]
        out += [(it, False) for it in d["items"] if placement_key(it) == p["key"]]
        return out

    def flow_for(self, it, p, from_master=False):
        """Composition à utiliser pour un bloc texte posé sur la page p."""
        if from_master or "m" in it["on"]:
            return self.master_flow(it, p["num"] if p["kind"] == "page" else None)
        return self.flows.get(it.get("story"))

    def draw_item(self, qp, it, ox, oy, p, from_master, screen=True, extra=None):
        """Dessine un bloc. ox, oy : origine de la page en points."""
        w, h = it["w"] * MM, it["h"] * MM
        qp.save()
        qp.setTransform(item_xf(it, ox, oy), True)
        r = QRectF(0, 0, w, h)
        fill = swatch_qcolor(self.doc, it["fill"]) if it.get("fill") else None
        ell = it["type"] == "ellipse"
        qp.setPen(Qt.NoPen)
        if fill is not None:
            qp.setBrush(QBrush(fill))
            qp.drawEllipse(r) if ell else qp.drawRect(r)
        if it["type"] == "image":
            img = self.qimage(it.get("asset")) if it.get("asset") else None
            if img is not None and not img.isNull():
                iw, ih = img.width(), img.height()
                fit = it.get("fit", "cover")
                if fit == "fill":
                    dw, dh = w, h
                else:
                    s = (min if fit == "contain" else max)(w / iw, h / ih)
                    dw, dh = iw * s, ih * s
                tx = (w - dw) * it.get("fx", 50) / 100
                ty = (h - dh) * it.get("fy", 50) / 100
                qp.save(); qp.setClipRect(r, Qt.IntersectClip)
                qp.drawImage(QRectF(tx, ty, dw, dh), img)
                qp.restore()
            elif screen:
                qp.setPen(QPen(QColor(150, 150, 150), 0))
                qp.drawLine(r.topLeft(), r.bottomRight()); qp.drawLine(r.topRight(), r.bottomLeft())
        if it["type"] == "text":
            ins = (it.get("inset") or 0) * MM
            fl = self.flow_for(it, p, from_master)
            if extra:  # sélection de texte (édition sur la page)
                extra(qp, ins)
            if fl:
                org = QPointF(ins, ins)
                for e in fl.frames.get(it["id"], []):
                    for i in e.lines:
                        e.layout.lineAt(i).draw(qp, org)
        if it.get("stroke") and it.get("sw", 0) > 0:
            qp.setBrush(Qt.NoBrush)
            pen = QPen(swatch_qcolor(self.doc, it["stroke"]), it["sw"]); pen.setJoinStyle(Qt.MiterJoin)
            qp.setPen(pen)
            qp.drawEllipse(r) if ell else qp.drawRect(r)
        qp.restore()
