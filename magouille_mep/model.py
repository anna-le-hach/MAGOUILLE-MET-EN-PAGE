"""Modèle du document (projets enregistrés en JSON).
Positions en millimètres, typo en points."""
import copy, random, string, html
from html.parser import HTMLParser

MM = 72 / 25.4          # 1 mm en points
FORMATS = {"A3": (297, 420), "A4": (210, 297), "A5": (148, 210), "A6": (105, 148),
           "Carré 150": (150, 150), "Carré 210": (210, 210), "US Letter": (215.9, 279.4), "Carte postale": (100, 150)}
BUILTIN_FONTS = ["Work Sans", "IBM Plex Sans", "EB Garamond", "Libre Baskerville", "IBM Plex Serif", "Fraunces", "Space Mono", "Bebas Neue"]


def uid(p=""):
    return p + "".join(random.choices(string.ascii_lowercase + string.digits, k=7))


def r2(v):
    return round(v * 100) / 100


def default_swatches():
    return [
        {"id": "noir", "name": "Noir", "mode": "cmyk", "c": 0, "m": 0, "y": 0, "k": 100},
        {"id": "papier", "name": "Papier", "mode": "cmyk", "c": 0, "m": 0, "y": 0, "k": 0},
        {"id": "gris", "name": "Gris 40 %", "mode": "cmyk", "c": 0, "m": 0, "y": 0, "k": 40},
        {"id": "rouge", "name": "Rouge", "mode": "cmyk", "c": 0, "m": 85, "y": 80, "k": 0},
        {"id": "bleu", "name": "Bleu", "mode": "cmyk", "c": 90, "m": 60, "y": 0, "k": 0},
        {"id": "jaune", "name": "Jaune", "mode": "cmyk", "c": 0, "m": 10, "y": 95, "k": 0},
    ]


def default_styles():
    b = dict(font="EB Garamond", size=11, lead=14, weight=400, ital=False, align="justify", color="noir",
             sb=0, sa=0, ind=0, track=0, caps=False, hyph=True)
    return [
        {**b, "id": "corps", "name": "Corps de texte", "ind": 5},
        {**b, "id": "titre", "name": "Titre", "font": "Work Sans", "size": 28, "lead": 30, "weight": 700, "align": "left", "sa": 6, "hyph": False},
        {**b, "id": "intertitre", "name": "Intertitre", "font": "Work Sans", "size": 13, "lead": 16, "weight": 700, "align": "left", "sb": 4, "sa": 2, "hyph": False},
        {**b, "id": "chapo", "name": "Chapô", "size": 14, "lead": 18, "ital": True, "align": "left", "sa": 4, "hyph": False},
        {**b, "id": "legende", "name": "Légende", "font": "Work Sans", "size": 8, "lead": 10, "align": "left", "color": "gris"},
        {**b, "id": "folio", "name": "Folio", "font": "Work Sans", "size": 8, "lead": 10, "align": "center", "hyph": False},
    ]


def new_doc(name="Sans titre", w=148, h=210, bleed=3, facing=True, margins=None, cols=1, gutter=5, pages=8):
    margins = margins or {"t": 15, "b": 20, "i": 18, "o": 14}
    d = {"v": 1, "name": name, "w": w, "h": h, "bleed": bleed, "facing": facing, "margins": dict(margins),
         "cols": cols, "gutter": gutter, "pages": [], "masters": [{"id": "A", "name": "A-Gabarit"}],
         "items": [], "stories": {}, "styles": default_styles(), "charStyles": default_char_styles(), "swatches": default_swatches(), "customFonts": []}
    for _ in range(pages):
        d["pages"].append({"id": uid("p"), "m": "A"})
    for s in ("L", "R"):  # folio en bas des pages du gabarit
        iid, sid = uid("i"), uid("s")
        d["stories"][sid] = {"paras": [{"s": "folio", "h": "{n}"}], "frames": [iid]}
        d["items"].append({"id": iid, "type": "text", "on": {"m": "A", "s": s},
                           "x": margins["o"] if s == "L" else margins["i"], "y": h - margins["b"] + 6,
                           "w": w - margins["i"] - margins["o"], "h": 6, "story": sid, "inset": 0,
                           "fill": None, "stroke": None, "sw": 0.5})
    return d


class Doc:
    """Petites aides autour du dictionnaire du document."""
    def __init__(self, d, assets=None):
        self.d = d
        self.assets = assets or {}
        d.setdefault("customFonts", [])
        d.setdefault("charStyles", default_char_styles())

    # accès
    def style(self, sid):
        for s in self.d["styles"]:
            if s["id"] == sid:
                return s
        return self.d["styles"][0]

    def char_style(self, cid):
        for s in self.d.get("charStyles", []):
            if s["id"] == cid:
                return s
        return None

    def swatch(self, sid):
        for s in self.d["swatches"]:
            if s["id"] == sid:
                return s
        return None

    def item(self, iid):
        for i in self.d["items"]:
            if i["id"] == iid:
                return i
        return None

    def page_side(self, i):
        if not self.d["facing"]:
            return "R"
        return "R" if i % 2 == 0 else "L"

    def margins_for(self, side):
        m = self.d["margins"]
        return {"l": m["o"], "r": m["i"], "t": m["t"], "b": m["b"]} if side == "L" else {"l": m["i"], "r": m["o"], "t": m["t"], "b": m["b"]}

    def spreads(self):
        """Liste de groupes d'index de pages (planches)."""
        out, n, i = [], len(self.d["pages"]), 0
        while i < n:
            grp = ([0] if i == 0 else [k for k in (i, i + 1) if k < n]) if self.d["facing"] else [i]
            out.append(grp)
            i += len(grp)
        return out

    def remove_frame_from_story(self, it):
        st = self.d["stories"].get(it.get("story"))
        if not st:
            return
        st["frames"] = [f for f in st["frames"] if f != it["id"]]
        if not st["frames"]:
            del self.d["stories"][it["story"]]

    def used_assets(self):
        return {it["asset"]: self.assets[it["asset"]] for it in self.d["items"] if it.get("asset") in self.assets}


def placement_key(it):
    on = it["on"]
    return on["p"] if "p" in on else f"M:{on['m']}:{on['s']}"


# ---------- Paragraphes : petit HTML (<b>, <i>, <span data-cs>, <br>) <-> texte + plages de format ----------
# Une plage = (début, longueur, gras, italique, style_de_caractère_ou_None)
NOATTR = (False, False, None)


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.attrs, self.b, self.i, self.cs = "", [], 0, 0, []

    def handle_starttag(self, tag, a):
        if tag in ("b", "strong"): self.b += 1
        elif tag in ("i", "em"): self.i += 1
        elif tag == "br": self.handle_data("\u2028")
        elif tag == "span": self.cs.append(dict(a).get("data-cs"))

    def handle_endtag(self, tag):
        if tag in ("b", "strong"): self.b = max(0, self.b - 1)
        elif tag in ("i", "em"): self.i = max(0, self.i - 1)
        elif tag == "span" and self.cs: self.cs.pop()

    def handle_data(self, data):
        if not data: return
        cs = next((c for c in reversed(self.cs) if c), None)
        self.text += data
        self.attrs += [(bool(self.b), bool(self.i), cs)] * len(data)


def para_chars(h):
    """HTML du paragraphe -> (texte, attributs par caractère)."""
    p = _P(); p.feed(h or ""); p.close()
    return p.text, p.attrs


def chars_para(text, attrs):
    """(texte, attributs par caractère) -> HTML du paragraphe."""
    out, cur = "", NOATTR
    def close(c):
        return ("</i>" if c[1] else "") + ("</b>" if c[0] else "") + ("</span>" if c[2] else "")
    def open_(c):
        return (f'<span data-cs="{c[2]}">' if c[2] else "") + ("<b>" if c[0] else "") + ("<i>" if c[1] else "")
    for ch, a in zip(text, attrs):
        if a != cur:
            out += close(cur) + open_(a); cur = a
        out += "<br>" if ch == "\u2028" else html.escape(ch, quote=False)
    return out + close(cur)


def runs_of(attrs):
    out, i = [], 0
    while i < len(attrs):
        j = i
        while j < len(attrs) and attrs[j] == attrs[i]: j += 1
        if attrs[i] != NOATTR: out.append((i, j - i) + tuple(attrs[i]))
        i = j
    return out


def parse_para(h):
    """Renvoie (texte, [(début, longueur, gras, italique, style_car)])."""
    t, a = para_chars(h)
    return t, runs_of(a)


def build_para(text, runs):
    attrs = [NOATTR] * len(text)
    for r in runs:
        st, ln = r[0], r[1]
        for k in range(st, min(len(text), st + ln)): attrs[k] = (r[2], r[3], r[4] if len(r) > 4 else None)
    return chars_para(text, attrs)


def default_char_styles():
    return [
        {"id": "accent", "name": "Accent", "font": None, "weight": None, "ital": True, "size": None, "color": "rouge", "track": None, "caps": None, "under": False},
        {"id": "petitescap", "name": "Capitales espacées", "font": None, "weight": None, "ital": None, "size": None, "color": None, "track": 80, "caps": True, "under": False},
    ]


FAUX_TEXTE = [
    "Le papier a un sens, comme le bois a un fil. Quand on plie dans le bon sens, le pli est net et la page tombe bien ; dans l’autre sens, elle résiste, gondole et finit par se fendre au dos.",
    "Une signature, c’est une feuille pliée plusieurs fois sur elle-même. On les assemble, on les coud ensemble, et le livre prend forme cahier après cahier. Avant de coudre, il faut pourtant que chaque page soit à sa place : c’est tout le travail de l’imposition.",
    "Dans une mise en page, le blanc compte autant que le texte. Des marges généreuses laissent respirer la page et donnent de la place aux pouces du lecteur. Une colonne trop large fatigue l’œil, une colonne trop étroite hache la lecture.",
    "Choisir un caractère, c’est choisir une voix. Un garalde murmure, une linéale parle net, une égyptienne pose ses empattements comme on pose ses coudes sur la table. Il suffit souvent de deux familles pour faire tout un livre.",
]


def example_doc():
    d = new_doc(name="Mon premier zine", pages=8)
    d["pages"][0]["m"] = ""
    d["swatches"].append({"id": "creme", "name": "Crème", "mode": "cmyk", "c": 0, "m": 4, "y": 18, "k": 0})
    titre = next(s for s in d["styles"] if s["id"] == "titre")
    d["styles"].append({**titre, "id": "couv", "name": "Titre couverture", "size": 46, "lead": 44, "color": "creme", "font": "Bebas Neue", "weight": 400})
    def add(pi, **o):
        it = {"id": uid("i"), "on": {"p": d["pages"][pi]["id"]}, "fill": None, "stroke": None, "sw": 0.5}
        it.update(o); d["items"].append(it); return it
    def story(paras, ids):
        sid = uid("s"); d["stories"][sid] = {"paras": paras, "frames": ids}; return sid
    add(0, type="rect", x=-3, y=-3, w=154, h=216, fill="rouge")
    t1 = uid("i")
    add(0, id=t1, type="text", x=14, y=22, w=120, h=70, inset=0,
        story=story([{"s": "couv", "h": "Mon premier zine"}, {"s": "chapo", "h": "<i>Fabriqué avec Magouille met en page</i>"}], [t1]))
    add(0, type="ellipse", x=84, y=128, w=46, h=46, fill="jaune")
    a, b = uid("i"), uid("i")
    body = [
        {"s": "titre", "h": "Comment ça marche"},
        {"s": "chapo", "h": "Ce texte coule d’un bloc à l’autre, de la page 2 à la page 3. Clique dessus pour voir le fil qui relie les deux blocs."},
        {"s": "intertitre", "h": "Les blocs"},
        {"s": "corps", "h": "Tout ce qui est posé sur la page est un bloc : du texte, une image, un rectangle ou une ellipse. On les trace avec les outils à gauche, on les déplace à la souris ou aux flèches du clavier. Les bords des marges et des colonnes sont <b>magnétiques</b> : les blocs viennent s’y coller tout seuls."},
        {"s": "intertitre", "h": "Les styles"},
        {"s": "corps", "h": "Chaque paragraphe a un style : titre, intertitre, corps de texte… Dans l’onglet Styles, change la police ou le corps du style « Corps de texte » et regarde tout le texte suivre d’un coup. C’est ça, la force d’une feuille de styles : on décide une fois, on applique partout."},
        *[{"s": "corps", "h": html.escape(t, quote=False)} for t in FAUX_TEXTE],
        {"s": "intertitre", "h": "Les gabarits"},
        {"s": "corps", "h": "Le numéro en bas de chaque page vient du gabarit A. Modifie-le une fois dans le panneau de gauche, toutes les pages suivent. La couverture n’utilise pas de gabarit, c’est pour ça qu’elle n’a pas de folio."},
        {"s": "legende", "h": "Astuce : glisse une photo depuis ton ordinateur directement dans le bloc image ci-contre."},
    ]
    sid = story(body, [a, b])
    m = d["margins"]
    add(1, id=a, type="text", x=m["o"], y=m["t"], w=d["w"] - m["i"] - m["o"], h=d["h"] - m["t"] - m["b"], inset=0, story=sid)
    add(2, id=b, type="text", x=m["i"], y=m["t"] + 80, w=d["w"] - m["i"] - m["o"], h=d["h"] - m["t"] - m["b"] - 80, inset=0, story=sid)
    add(2, type="image", x=m["i"], y=m["t"], w=d["w"] - m["i"] - m["o"], h=74, asset=None, fit="cover", fx=50, fy=50)
    return d
