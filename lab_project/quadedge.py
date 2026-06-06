"""Структура даних «кільце-ребро» (quad-edge) Гібаса–Столфі.

Кожне неорієнтоване ребро подане групою з 4 напрямлених записів:
  e        -- саме ребро (origin -> dest)
  e.rot    -- дуальне ребро, повернуте на +90 (ребро Вороного)
  e.sym    -- те саме ребро у зворотному напрямку
  e.invrot -- дуальне ребро, повернуте на -90
Поле ``data`` напрямленого ребра — його точка-початок (origin).

На цій структурі тримаються обидві діаграми одночасно: первинні ребра
дають тріангуляцію Делоне, а їхні ``rot``-двійники — діаграму Вороного.
"""


class Edge:
    __slots__ = ("onext", "rot", "data")

    def __init__(self):
        self.onext = None  # наступне ребро навколо origin (проти годинника)
        self.rot = None    # дуальне ребро (поворот на +90)
        self.data = None   # точка-початок (origin)

    # --- похідні навігаційні ребра (формули Гібаса–Столфі) ---
    @property
    def sym(self):
        return self.rot.rot

    @property
    def invrot(self):
        return self.rot.rot.rot

    @property
    def oprev(self):
        return self.rot.onext.rot

    @property
    def lnext(self):
        return self.invrot.onext.rot

    @property
    def rprev(self):
        return self.sym.onext

    @property
    def org(self):
        return self.data

    @property
    def dest(self):
        return self.rot.rot.data


def make_edge(org, dest):
    """Створити ізольоване ребро org -> dest, повернути його primary-запис."""
    e = [Edge(), Edge(), Edge(), Edge()]
    e[0].rot, e[1].rot, e[2].rot, e[3].rot = e[1], e[2], e[3], e[0]
    e[0].onext, e[2].onext = e[0], e[2]
    e[1].onext, e[3].onext = e[3], e[1]
    e[0].data = org
    e[2].data = dest
    return e[0]


def splice(a, b):
    """Базова операція Гібаса–Столфі: склеює/розриває кільця двох ребер."""
    alpha = a.onext.rot
    beta = b.onext.rot
    a.onext, b.onext = b.onext, a.onext
    alpha.onext, beta.onext = beta.onext, alpha.onext


def connect(a, b):
    """З'єднати dest(a) з org(b) новим ребром у тій самій грані."""
    e = make_edge(a.dest, b.org)
    splice(e, a.lnext)
    splice(e.sym, b)
    return e


def delete_edge(e):
    """Вилучити ребро зі структури."""
    splice(e, e.oprev)
    splice(e.sym, e.sym.oprev)


def enumerate_edges(start):
    """Усі напрямлені ребра, досяжні від ``start`` (обхід кілець onext)."""
    if start is None:
        return []
    result = []
    visited = set()
    stack = [start]
    while stack:
        e = stack.pop()
        if id(e) in visited:
            continue
        cur = e
        while True:
            if id(cur) not in visited:
                visited.add(id(cur))
                result.append(cur)
                stack.append(cur.sym)
            cur = cur.onext
            if cur is e:
                break
    return result
