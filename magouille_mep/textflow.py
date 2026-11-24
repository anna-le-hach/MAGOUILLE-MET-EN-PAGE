"""Composition du texte : paragraphes -> lignes, qui coulent d'un bloc à l'autre.
Toutes les mesures sont en points (1/72 pouce) : on compose sur un périphérique à 72 ppp."""
import re
from functools import lru_cache
from PySide6.QtGui import QImage, QFont, QTextLayout, QTextOption, QTextCharFormat, QColor
from PySide6.QtCore import Qt, QPointF
from .model import MM, parse_para

try:
    import pyphen
    _HY = pyphen.Pyphen(lang="fr_FR")
except Exception:  # césure optionnelle
    _HY = None

_DEV = None


def device():
    global _DEV
    if _DEV is None:
        _DEV = QImage(4, 4, QImage.Format_ARGB32)
        _DEV.setDotsPerMeterX(2835)   # 72 ppp
        _DEV.setDotsPerMeterY(2835)
    return _DEV


def swatch_qcolor(doc, sid):
    s = doc.swatch(sid)
    if not s:
        return QColor(0, 0, 0)
    if s.get("mode") == "rgb":
        return QColor(s.get("hex", "#000000"))
    return QColor.fromCmykF(s["c"] / 100, s["m"] / 100, s["y"] / 100, s["k"] / 100)


def make_font(st, bold=None, italic=None):
    f = QFont(st["font"])
    f.setPointSizeF(max(1.0, float(st["size"])))
    f.setWeight(QFont.Bold if (bold if bold is not None else st["weight"] >= 600) else QFont.Normal)
    f.setItalic(bool(italic if italic is not None else st["ital"]))
    f.setHintingPreference(QFont.PreferNoHinting)
    f.setStyleStrategy(QFont.PreferAntialias)
    if st.get("track"):
        f.setLetterSpacing(QFont.AbsoluteSpacing, st["size"] * st["track"] / 1000)
    if st.get("caps"):
        f.setCapitalization(QFont.AllUppercase)
    return f


_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ’']{6,}")


@lru_cache(maxsize=4096)
def _hyph_text(text):
    """Texte avec césures conditionnelles (U+00AD) + table ancien index -> nouvel index."""
    if not _HY or not text:
        return text, tuple(range(len(text) + 1))
    out, pos = [], 0
    for m in _WORD.finditer(text):
        out.append(text[pos:m.start()])
        out.append(_HY.inserted(m.group(0), hyphen="\u00ad"))
        pos = m.end()
    out.append(text[pos:])
    new = "".join(out)
    idx, j = [], 0
    for ch in text:
        while j < len(new) and new[j] == "\u00ad" and ch != "\u00ad":
            j += 1
        idx.append(j); j += 1
    idx.append(len(new))
    return new, tuple(idx)


def hyphenate(text, runs):
    new, idx = _hyph_text(text)
    return new, [(idx[r[0]], idx[min(len(text), r[0] + r[1])] - idx[r[0]]) + tuple(r[2:]) for r in runs], idx


class Entry:
    """Un morceau de paragraphe posé dans un bloc."""
    __slots__ = ("layout", "lines", "para", "base", "map", "frame")

    def __init__(self, layout, lines, para, base, map_, frame):
        self.layout, self.lines, self.para, self.base, self.map, self.frame = layout, lines, para, base, map_, frame


class Flow:
    """Résultat de composition d'un texte."""
    def __init__(self):
        self.frames = {}      # clé du bloc -> [Entry]
        self.overset = False
        self.keep = []

    def entries(self):
        for k, lst in self.frames.items():
            for e in lst:
                yield e


def char_format(doc, st, b, i, cs, col):
    cf = QTextCharFormat(); cf.setForeground(col)
    c = doc.char_style(cs) if cs else None
    weight_bold = b or (c and c.get("weight") and c["weight"] >= 600)
    if c and c.get("weight") is not None and c["weight"] < 600 and not b:
        cf.setFontWeight(QFont.Normal)
    elif weight_bold:
        cf.setFontWeight(QFont.Bold)
    if i or (c and c.get("ital")):
        cf.setFontItalic(True)
    elif c and c.get("ital") is False:
        cf.setFontItalic(False)
    if c:
        if c.get("font"): cf.setFontFamilies([c["font"]])
        if c.get("size"): cf.setFontPointSize(float(c["size"]))
        if c.get("color"): cf.setForeground(swatch_qcolor(doc, c["color"]))
        if c.get("track") is not None:
            size = float(c.get("size") or st["size"])
            cf.setFontLetterSpacingType(QFont.AbsoluteSpacing); cf.setFontLetterSpacing(size * c["track"] / 1000)
        if c.get("caps") is not None:
            cf.setFontCapitalization(QFont.AllUppercase if c["caps"] else QFont.MixedCase)
        if c.get("under"): cf.setFontUnderline(True)
    return cf


def _layout(doc, st, text, runs):
    f = make_font(st)
    lay = QTextLayout(text, f, device())
    opt = QTextOption()
    al = {"left": Qt.AlignLeft, "center": Qt.AlignHCenter, "right": Qt.AlignRight, "justify": Qt.AlignJustify}[st.get("align", "left")]
    opt.setAlignment(al)
    opt.setUseDesignMetrics(True)
    opt.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
    lay.setTextOption(opt)
    col = swatch_qcolor(doc, st.get("color"))
    base = QTextCharFormat(); base.setForeground(col)
    r = QTextLayout.FormatRange(); r.start, r.length, r.format = 0, len(text), base
    fmts = [r]
    for run in runs:
        s, l, b, i = run[:4]
        cs = run[4] if len(run) > 4 else None
        rr = QTextLayout.FormatRange(); rr.start, rr.length, rr.format = s, l, char_format(doc, st, b, i, cs, col)
        fmts.append(rr)
    lay.setFormats(fmts)
    return lay


def folio(h, n, total):
    return h.replace("{n}", str(n)).replace("{t}", str(total))


def flow_story(doc, paras, frames, total_pages):
    """frames : liste (clé, largeur_pt, hauteur_pt, numéro_de_page). Renvoie un Flow."""
    res = Flow()
    queue = [{"s": p["s"], "h": p["h"], "cont": False, "pi": k} for k, p in enumerate(paras)]
    for key, W, H, n in frames:
        res.frames[key] = []
        y, first_in_frame = 0.0, True
        while queue:
            q = queue[0]
            st = doc.style(q["s"])
            if "text" not in q:
                t, runs = parse_para(folio(q["h"], n, total_pages) if (n is not None and "{" in q["h"]) else q["h"])
                if st.get("hyph"):
                    t, runs, mp = hyphenate(t, runs)
                else:
                    mp = tuple(range(len(t) + 1))
                q.update(text=t, runs=runs, map=mp, base=0)
            text, runs, cont = q["text"], q["runs"], q["cont"]
            lead = float(st["lead"])
            sb = 0 if (first_in_frame or cont) else st["sb"] * MM
            ind = 0 if cont else st["ind"] * MM
            lay = _layout(doc, st, text, runs)
            res.keep.append(lay)
            lay.beginLayout()
            ly, placed, split_at, k = y + sb, [], None, 0
            while True:
                line = lay.createLine()
                if not line.isValid():
                    break
                x0 = ind if (k == 0 and ind > 0) else 0
                line.setLineWidth(max(1.0, W - (abs(ind) if k == 0 else 0)))
                if ly + lead > H + 0.01:
                    split_at = line.textStart(); break
                h = line.ascent() + line.descent()
                line.setPosition(QPointF(x0, ly + (lead - h) / 2))
                placed.append(k); ly += lead; k += 1
            lay.endLayout()
            if placed:
                res.frames[key].append(Entry(lay, placed, q["pi"], q["base"], q["map"], key))
            if split_at is None:
                queue.pop(0)
                y = ly + st["sa"] * MM
                first_in_frame = False
                continue
            if split_at > 0 and placed:
                rest = text[split_at:]
                nruns = []
                for r in runs:
                    s0, l0 = r[0], r[1]
                    a, e = max(s0, split_at), min(s0 + l0, len(text))
                    if e > a:
                        nruns.append((a - split_at, e - a) + tuple(r[2:]))
                queue[0] = {"s": q["s"], "h": "", "cont": True, "text": rest, "runs": nruns, "pi": q["pi"], "map": q["map"], "base": q["base"] + split_at}
            break
    res.overset = bool(queue)
    return res
