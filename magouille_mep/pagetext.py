"""Saisie du texte directement sur la page : curseur, sélection, frappe, styles."""
import re
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence
from .model import para_chars, chars_para, NOATTR, MM
from .render import item_xf

WORDCH = re.compile(r"\w", re.UNICODE)


class PageText:
    def __init__(self, win, sid):
        self.win, self.sid = win, sid
        self.caret = self.anchor = (0, 0)
        self.pending = None            # attributs pour la prochaine frappe
        self.goal_x = None             # colonne visée pour haut/bas
        self.blink_on = True
        self.timer = QTimer(); self.timer.setInterval(530); self.timer.timeout.connect(self._blink); self.timer.start()

    # ------------------------------------------------------------ accès
    @property
    def D(self): return self.win.doc
    @property
    def story(self): return self.D.d["stories"].get(self.sid)

    def paras(self): return self.story["paras"]

    def chars(self, k):
        return para_chars(self.paras()[k]["h"])

    def plen(self, k):
        return len(self.chars(k)[0])

    def stop(self):
        self.timer.stop()

    def _blink(self):
        self.blink_on = not self.blink_on
        self.win.canvas.update()

    def poke(self):
        self.blink_on = True; self.timer.start()

    def sel(self):
        return (min(self.caret, self.anchor), max(self.caret, self.anchor))

    def has_sel(self):
        return self.caret != self.anchor

    def clamp(self):
        ps = self.paras()
        def c(pos):
            p = min(max(0, pos[0]), len(ps) - 1)
            return (p, min(max(0, pos[1]), self.plen(p)))
        self.caret, self.anchor = c(self.caret), c(self.anchor)

    # ------------------------------------------------------------ géométrie
    def frames(self):
        """[(item, placement, flow)] pour les blocs visibles du texte."""
        R, out = self.win.renderer, []
        for fid in self.story["frames"]:
            it = self.D.item(fid)
            if not it: continue
            from .model import placement_key
            p = R.pl(placement_key(it))
            if not p: continue
            out.append((it, p, R.flow_for(it, p)))
        return out

    def lines(self):
        """Toutes les lignes visibles dans l'ordre : (item, placement, entry, index_ligne)."""
        out = []
        for it, p, fl in self.frames():
            if not fl: continue
            for e in fl.frames.get(it["id"], []):
                for li in e.lines:
                    out.append((it, p, e, li))
        return out

    @staticmethod
    def to_orig(e, laid):
        m = e.map; o = 0
        for k, v in enumerate(m):
            if v <= laid: o = k
            else: break
        return o

    def locate(self, pos):
        """Ligne et x (repère du layout) d'une position, ou None si invisible (texte en excès)."""
        p, o = pos
        cands = [(it, pl, e, li) for it, pl, e, li in self.lines() if e.para == p]
        if not cands: return None
        best = None
        for it, pl, e, li in cands:
            local = e.map[min(o, len(e.map) - 1)] - e.base
            ln = e.layout.lineAt(li)
            st, en = ln.textStart(), ln.textStart() + ln.textLength()
            if st <= local < en:
                best = (it, pl, e, li, local); break
            if local == en:
                best = (it, pl, e, li, local)
        if not best:
            return None
        it, pl, e, li, local = best
        x = e.layout.lineAt(li).cursorToX(local)
        x = x[0] if isinstance(x, tuple) else x
        return it, pl, e, li, x

    def hit(self, bx, by):
        """Position du texte sous un point de la table (mm), ou None."""
        best, bd = None, 1e9
        for it, p, fl in self.frames():
            if not fl: continue
            inv, ok = item_xf(it, p["x"], p["y"], 1).inverted()
            lp = inv.map(QPointF(bx, by))
            if not (-1 <= lp.x() <= it["w"] + 1 and -1 <= lp.y() <= it["h"] + 1): continue
            ins = (it.get("inset") or 0)
            x, y = (lp.x() - ins) * MM, (lp.y() - ins) * MM
            entries = fl.frames.get(it["id"], [])
            for e in entries:
                for li in e.lines:
                    ln = e.layout.lineAt(li)
                    top, bot = ln.y(), ln.y() + ln.height()
                    d = 0 if top <= y <= bot else min(abs(y - top), abs(y - bot))
                    if d < bd:
                        bd = d
                        c = ln.xToCursor(x)
                        best = (e.para, self.to_orig(e, e.base + c))
            if best is None:  # bloc vide
                best = (len(self.paras()) - 1, self.plen(len(self.paras()) - 1)) if not entries else best
            if best: return best
        return None

    # ------------------------------------------------------------ dessin
    def paint_extra(self, it):
        """Fonction appelée dans le repère du bloc (points) pour peindre sélection et curseur."""
        def draw(qp, ins):
            a, b = self.sel()
            if self.has_sel():
                qp.save(); qp.setPen(Qt.NoPen); qp.setBrush(QColor(58, 111, 240, 70))
                for it2, pl, e, li in self.lines():
                    if it2["id"] != it["id"] or not (a[0] <= e.para <= b[0]): continue
                    n = len(e.map) - 1
                    oa = a[1] if e.para == a[0] else 0
                    ob = b[1] if e.para == b[0] else n
                    la, lb = e.map[oa] - e.base, e.map[ob] - e.base
                    ln = e.layout.lineAt(li)
                    s0, s1 = ln.textStart(), ln.textStart() + ln.textLength()
                    x0, x1 = max(la, s0), min(lb, s1)
                    if x1 < x0 or (x1 == x0 and not (e.para < b[0] and x1 == s1)): continue
                    X0 = ln.cursorToX(x0); X1 = ln.cursorToX(x1)
                    X0 = X0[0] if isinstance(X0, tuple) else X0; X1 = X1[0] if isinstance(X1, tuple) else X1
                    if e.para < b[0] and x1 == s1 and ob == n: X1 += 3
                    qp.drawRect(QRectF(ins + min(X0, X1), ins + ln.y(), abs(X1 - X0), ln.height()))
                qp.restore()
            if self.blink_on:
                loc = self.locate(self.caret)
                if loc and loc[0]["id"] == it["id"]:
                    _, _, e, li, x = loc
                    ln = e.layout.lineAt(li)
                    qp.fillRect(QRectF(ins + x - 0.25, ins + ln.y(), 0.6, ln.height()), QColor(20, 20, 20))
        return draw

    def caret_rect_board(self):
        """Rectangle du curseur sur la table (mm), pour le défilement et la saisie de texte."""
        loc = self.locate(self.caret)
        if not loc: return None
        it, pl, e, li, x = loc
        ln = e.layout.lineAt(li); ins = it.get("inset") or 0
        t = item_xf(it, pl["x"], pl["y"], 1)
        return t.mapRect(QRectF(ins + x / MM, ins + ln.y() / MM, 0.3, ln.height() / MM))

    # ------------------------------------------------------------ modifications
    def _write(self, k, text, attrs):
        self.paras()[k]["h"] = chars_para(text, attrs)

    def _changed(self):
        self.clamp(); self.poke(); self.win.page_text_changed(self.sid)

    def _commit(self, kind="type"):
        self.win.commit(merge=f"{kind}:{self.sid}")

    def delete_sel(self):
        if not self.has_sel(): return False
        (pa, oa), (pb, ob) = self.sel()
        ta, aa = self.chars(pa); tb, ab = self.chars(pb)
        self._write(pa, ta[:oa] + tb[ob:], aa[:oa] + ab[ob:])
        del self.paras()[pa + 1:pb + 1]
        self.caret = self.anchor = (pa, oa)
        return True

    def typing_attrs(self):
        if self.pending is not None: return self.pending
        p, o = self.caret; t, a = self.chars(p)
        o = min(o, len(a))
        if o > 0: return a[o - 1]
        return a[0] if a else NOATTR

    def insert(self, s):
        if not s: return
        self._commit()
        attrs = self.typing_attrs()
        self.delete_sel()
        parts = s.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        p, o = self.caret
        t, a = self.chars(p)
        head_t, head_a, tail_t, tail_a = t[:o], a[:o], t[o:], a[o:]
        if len(parts) == 1:
            self._write(p, head_t + s + tail_t, head_a + [attrs] * len(s) + tail_a)
            self.caret = self.anchor = (p, o + len(s))
        else:
            style = self.paras()[p]["s"]
            self._write(p, head_t + parts[0], head_a + [attrs] * len(parts[0]))
            for k, part in enumerate(parts[1:], 1):
                last = k == len(parts) - 1
                tt = part + (tail_t if last else ""); aa = [attrs] * len(part) + (tail_a if last else [])
                self.paras().insert(p + k, {"s": style, "h": chars_para(tt, aa)})
            self.caret = self.anchor = (p + len(parts) - 1, len(parts[-1]))
        self.pending = None if len(parts) == 1 else self.pending
        self._changed()

    def new_paragraph(self):
        self._commit("para")
        self.delete_sel()
        p, o = self.caret; t, a = self.chars(p)
        style = self.paras()[p]["s"]
        self._write(p, t[:o], a[:o])
        self.paras().insert(p + 1, {"s": style, "h": chars_para(t[o:], a[o:])})
        self.caret = self.anchor = (p + 1, 0)
        self._changed()

    def backspace(self, word=False):
        self._commit("del")
        if self.delete_sel(): return self._changed()
        p, o = self.caret
        if o == 0:
            if p == 0: return
            tp, ap = self.chars(p - 1); t, a = self.chars(p)
            self._write(p - 1, tp + t, ap + a); del self.paras()[p]
            self.caret = self.anchor = (p - 1, len(tp))
        else:
            t, a = self.chars(p)
            n = o - (self._word_left(t, o) if word else o - 1)
            self._write(p, t[:o - n] + t[o:], a[:o - n] + a[o:])
            self.caret = self.anchor = (p, o - n)
        self._changed()

    def delete(self, word=False):
        self._commit("del")
        if self.delete_sel(): return self._changed()
        p, o = self.caret; t, a = self.chars(p)
        if o >= len(t):
            if p >= len(self.paras()) - 1: return
            tn, an = self.chars(p + 1)
            self._write(p, t + tn, a + an); del self.paras()[p + 1]
        else:
            e = self._word_right(t, o) if word else o + 1
            self._write(p, t[:o] + t[e:], a[:o] + a[e:])
        self._changed()

    # ------------------------------------------------------------ mise en forme
    def toggle(self, idx):
        """idx 0 = gras, 1 = italique."""
        if not self.has_sel():
            a = list(self.typing_attrs()); a[idx] = not a[idx]; self.pending = tuple(a); self.win.page_text_caret(); return
        self._commit("fmt")
        (pa, oa), (pb, ob) = self.sel()
        first_t, first_a = self.chars(pa)
        on = not (first_a[oa][idx] if oa < len(first_a) else False)
        for k in range(pa, pb + 1):
            t, a = self.chars(k)
            s0 = oa if k == pa else 0; s1 = ob if k == pb else len(t)
            a = [tuple(on if j == idx else v for j, v in enumerate(x)) if s0 <= i < s1 else x for i, x in enumerate(a)]
            self._write(k, t, a)
        self._changed()

    def set_char_style(self, cid):
        cid = cid or None
        if not self.has_sel():
            a = list(self.typing_attrs()); a[2] = cid; self.pending = tuple(a); return
        self._commit("fmt")
        (pa, oa), (pb, ob) = self.sel()
        for k in range(pa, pb + 1):
            t, a = self.chars(k)
            s0 = oa if k == pa else 0; s1 = ob if k == pb else len(t)
            a = [(x[0], x[1], cid) if s0 <= i < s1 else x for i, x in enumerate(a)]
            self._write(k, t, a)
        self._changed()

    def set_para_style(self, sid):
        self._commit("fmt")
        (pa, _), (pb, _) = self.sel()
        for k in range(pa, pb + 1):
            self.paras()[k]["s"] = sid
        self._changed()

    def current_para_style(self):
        return self.paras()[self.caret[0]]["s"]

    def current_char_style(self):
        return self.typing_attrs()[2] or ""

    # ------------------------------------------------------------ déplacements
    @staticmethod
    def _word_left(t, o):
        while o > 0 and not WORDCH.match(t[o - 1]): o -= 1
        while o > 0 and WORDCH.match(t[o - 1]): o -= 1
        return o

    @staticmethod
    def _word_right(t, o):
        while o < len(t) and not WORDCH.match(t[o]): o += 1
        while o < len(t) and WORDCH.match(t[o]): o += 1
        return o

    def move(self, pos, extend):
        self.caret = pos
        if not extend: self.anchor = pos
        self.pending = None; self.poke(); self.win.page_text_caret()

    def left(self, extend, word=False):
        if self.has_sel() and not extend:
            return self.move(self.sel()[0], False)
        p, o = self.caret
        if o > 0:
            o = self._word_left(self.chars(p)[0], o) if word else o - 1
        elif p > 0:
            p -= 1; o = self.plen(p)
        self.goal_x = None; self.move((p, o), extend)

    def right(self, extend, word=False):
        if self.has_sel() and not extend:
            return self.move(self.sel()[1], False)
        p, o = self.caret; n = self.plen(p)
        if o < n:
            o = self._word_right(self.chars(p)[0], o) if word else o + 1
        elif p < len(self.paras()) - 1:
            p += 1; o = 0
        self.goal_x = None; self.move((p, o), extend)

    def vertical(self, d, extend):
        loc = self.locate(self.caret)
        if not loc:
            return
        L = self.lines()
        it, pl, e, li, x = loc
        k = next((i for i, t in enumerate(L) if t[2] is e and t[3] == li), None)
        if k is None: return
        if self.goal_x is None: self.goal_x = x
        k2 = k + d
        if k2 < 0: return self.move((0, 0), extend)
        if k2 >= len(L):
            last = len(self.paras()) - 1
            return self.move((last, self.plen(last)), extend)
        _, _, e2, li2 = L[k2]
        c = e2.layout.lineAt(li2).xToCursor(self.goal_x)
        gx = self.goal_x
        self.move((e2.para, self.to_orig(e2, e2.base + c)), extend); self.goal_x = gx

    def line_edge(self, end, extend):
        loc = self.locate(self.caret)
        if not loc: return
        it, pl, e, li, x = loc
        ln = e.layout.lineAt(li)
        local = ln.textStart() + (ln.textLength() if end else 0)
        o = self.to_orig(e, e.base + local)
        if end and o > 0 and o < self.plen(e.para) and self.chars(e.para)[0][o - 1] == " ":
            o -= 1
        self.goal_x = None; self.move((e.para, o), extend)

    def select_all(self):
        last = len(self.paras()) - 1
        self.anchor, self.caret = (0, 0), (last, self.plen(last)); self.poke(); self.win.page_text_caret()

    def select_word(self, pos):
        p, o = pos; t = self.chars(p)[0]
        a, b = o, o
        while a > 0 and WORDCH.match(t[a - 1]): a -= 1
        while b < len(t) and WORDCH.match(t[b]): b += 1
        self.anchor, self.caret = (p, a), (p, b); self.poke(); self.win.page_text_caret()

    def selected_text(self):
        (pa, oa), (pb, ob) = self.sel()
        out = []
        for k in range(pa, pb + 1):
            t = self.chars(k)[0]
            out.append(t[oa if k == pa else 0: ob if k == pb else len(t)])
        return "\n".join(out).replace(" ", "\n")

    # ------------------------------------------------------------ clavier
    def key(self, e):
        k, mod = e.key(), e.modifiers()
        ctrl = bool(mod & (Qt.ControlModifier | Qt.MetaModifier))
        shift = bool(mod & Qt.ShiftModifier)
        word = bool(mod & (Qt.ControlModifier | Qt.AltModifier))
        if e.matches(QKeySequence.Copy):
            if self.has_sel(): QGuiApplication.clipboard().setText(self.selected_text())
            return True
        if e.matches(QKeySequence.Cut):
            if self.has_sel():
                QGuiApplication.clipboard().setText(self.selected_text()); self._commit("cut"); self.delete_sel(); self._changed()
            return True
        if e.matches(QKeySequence.Paste):
            self.insert(QGuiApplication.clipboard().text()); return True
        if e.matches(QKeySequence.SelectAll):
            self.select_all(); return True
        if ctrl and k == Qt.Key_B: self.toggle(0); return True
        if ctrl and k == Qt.Key_I: self.toggle(1); return True
        if k == Qt.Key_Escape: self.win.end_page_text(); return True
        if k == Qt.Key_Left: self.left(shift, word); return True
        if k == Qt.Key_Right: self.right(shift, word); return True
        if k == Qt.Key_Up: self.vertical(-1, shift); return True
        if k == Qt.Key_Down: self.vertical(1, shift); return True
        if k == Qt.Key_Home:
            if ctrl: self.move((0, 0), shift)
            else: self.line_edge(False, shift)
            return True
        if k == Qt.Key_End:
            if ctrl: last = len(self.paras()) - 1; self.move((last, self.plen(last)), shift)
            else: self.line_edge(True, shift)
            return True
        if k == Qt.Key_Backspace: self.backspace(word); return True
        if k == Qt.Key_Delete: self.delete(word); return True
        if k in (Qt.Key_Return, Qt.Key_Enter):
            if shift: self.insert(" ")
            else: self.new_paragraph()
            return True
        if k == Qt.Key_Tab: self.insert("\t"); return True
        if ctrl:
            return False
        t = e.text()
        if t and t.isprintable():
            self.insert(t); return True
        return bool(t)
