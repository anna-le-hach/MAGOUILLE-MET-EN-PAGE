"""Export PDF vectoriel : polices incorporées, couleurs CMJN, fonds perdus, traits de coupe."""
from PySide6.QtGui import QPdfWriter, QPainter, QPageSize, QPen, QColor
from PySide6.QtCore import QSizeF, QMarginsF, QRectF, QPointF, Qt
from .model import MM
from . import APP_NAME


def export_pdf(win, path, first, last, bleed_on, marks, progress=None):
    R, D = win.renderer, win.doc
    d = D.d
    old = (R.mode, R.master)
    if R.mode != "pages":
        R.mode = "pages"; R.layout()
    R.reflow(); R.invalidate_masters()
    w, h = d["w"], d["h"]
    bl = d["bleed"] if bleed_on else 0
    mark_off, mark_len = max(bl, 2) + 1, 5
    S = mark_off + mark_len + 2 if marks else bl
    PW, PH = w + 2 * S, h + 2 * S
    wr = QPdfWriter(path)
    wr.setResolution(72)
    wr.setPageSize(QPageSize(QSizeF(PW, PH), QPageSize.Millimeter, "Page", QPageSize.ExactMatch))
    wr.setPageMargins(QMarginsF(0, 0, 0, 0))
    wr.setColorModel(QPdfWriter.ColorModel.CMYK)
    wr.setTitle(d["name"]); wr.setCreator(APP_NAME)
    qp = QPainter(wr)
    qp.setRenderHint(QPainter.Antialiasing); qp.setRenderHint(QPainter.TextAntialiasing)
    pls = [p for p in R.placements if p["kind"] == "page"]
    for n, pi in enumerate(range(first - 1, last)):
        if n: wr.newPage()
        P = next(p for p in pls if p["idx"] == pi)
        cl, cr = -bl, w + bl
        if d["facing"] and not P["alone"]:
            if P["side"] == "L": cr = w
            else: cl = 0
        qp.save()
        qp.setClipRect(QRectF((S + cl) * MM, (S - bl) * MM, (cr - cl) * MM, (h + 2 * bl) * MM))
        for sp in [p for p in pls if p["spread"] == P["spread"]]:
            ox, oy = (S + sp["x"] - P["x"]) * MM, S * MM
            for it, fm in R.items_for(sp):
                R.draw_item(qp, it, ox, oy, sp, fm, screen=False)
        qp.restore()
        if marks:
            pen = QPen(QColor.fromCmykF(1, 1, 1, 1), 0.25); qp.setPen(pen)
            for cx, sx in ((0, -1), (w, 1)):
                for cy, sy in ((0, -1), (h, 1)):
                    qp.drawLine(QPointF((S + cx + sx * mark_off) * MM, (S + cy) * MM), QPointF((S + cx + sx * (mark_off + mark_len)) * MM, (S + cy) * MM))
                    qp.drawLine(QPointF((S + cx) * MM, (S + cy + sy * mark_off) * MM), QPointF((S + cx) * MM, (S + cy + sy * (mark_off + mark_len)) * MM))
        if progress: progress(n + 1, last - first + 1)
    qp.end()
    del wr
    # TrimBox / BleedBox pour l'imprimeur
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import RectangleObject
        rd = PdfReader(path); out = PdfWriter()
        for pg in rd.pages:
            H = float(pg.mediabox.height)
            pg.trimbox = RectangleObject([S * MM, S * MM, (S + w) * MM, (S + h) * MM])
            pg.bleedbox = RectangleObject([(S - bl) * MM, (S - bl) * MM, (S + w + bl) * MM, (S + h + bl) * MM])
            out.add_page(pg)
        out.add_metadata({"/Title": d["name"], "/Creator": APP_NAME})
        with open(path, "wb") as f:
            out.write(f)
    except Exception as e:  # pypdf absent : le PDF reste valable sans ces boîtes
        print("TrimBox non ajoutée :", e)
    if old[0] != "pages":
        R.mode, R.master = old; R.layout()
