"""Явний розділяючий ланцюг Вороного з КЕШУВАННЯМ БІСЕКТРИС.

Це власна оптимізація прямого методу із завдання. Прямий метод будує
розділяючий ланцюг σ, на кожному кроці перетинаючи поточну бісектрису з
ребрами комірки — а це крихкі float-перетини «пряма×пряма».

Ключова ідея (кеш бісектрис як пар-породжувачів):
  кожне ребро Вороного — це бісектриса пари сайтів; точка зламу ланцюга —
  це перетин ДВОХ бісектрис B(p,q) ∩ B(p,r), що тотожний ЦЕНТРУ ОПИСАНОГО
  КОЛА трикутника (p, q, r):

        B(p,q) ∩ B(p,r)  ≡  circumcenter(p, q, r)

  Отже, кешуючи ребра як пари (i, j), кожен злам рахуємо ТОЧНО з трьох
  цілочисельних точок (без float-перетину прямих), а кільце quad-edge дає
  лише O(1) кандидатів на крок. Цим доводиться, що прямий ланцюг тотожний
  дуальному злиттю Делоне: O(N log N), але точно й без «глюків».

Модуль реконструює ланцюг кожного злиття під час побудови Делоне через
``recorder`` і вміє малювати його (як шар/анімацію в GUI).
"""

import math

from geometry import ccw, circumcenter, clip_segment
from quadedge import enumerate_edges
import delaunay


class BisectorCache:
    """Кеш бісектрис (рівняння прямих) та вершин (центрів кіл).

    Лічильники hits/misses демонструють повторне використання.
    """

    def __init__(self, points):
        self.pts = points
        self._line = {}
        self._vert = {}
        self.line_hits = self.line_miss = 0
        self.vert_hits = self.vert_miss = 0

    def line(self, i, j):
        """Серединний перпендикуляр пари (i, j): (A, B, C), A·x + B·y = C."""
        key = (i, j) if i < j else (j, i)
        v = self._line.get(key)
        if v is not None:
            self.line_hits += 1
            return v
        self.line_miss += 1
        p, q = self.pts[key[0]], self.pts[key[1]]
        A = q.x - p.x
        B = q.y - p.y
        C = (q.x * q.x - p.x * p.x + q.y * q.y - p.y * p.y) / 2.0
        self._line[key] = (A, B, C)
        return (A, B, C)

    def vertex(self, i, j, k):
        """Вершина Вороного = центр кола трикутника (i, j, k), з кешем."""
        key = (i, j, k)
        if key[0] > key[1]:
            key = (key[1], key[0], key[2])
        if key[1] > key[2]:
            key = (key[0], key[2], key[1])
        if key[0] > key[1]:
            key = (key[1], key[0], key[2])
        v = self._vert.get(key)
        if v is not None:
            self.vert_hits += 1
            return v
        self.vert_miss += 1
        a, b, c = self.pts[key[0]], self.pts[key[1]], self.pts[key[2]]
        cc = circumcenter(a, b, c)
        self._vert[key] = cc
        return cc


class _Chain:
    """Розділяючий ланцюг одного злиття: послідовність перехресних ребер.

    Перехресні ребра (basel) ніколи не вилучаються, тому їх можна
    реконструювати у фінальній структурі. Дуальне до кожного ребро
    Вороного — ланка ланцюга; перше/останнє відповідають σ_out/σ_in.
    """

    __slots__ = ("depth", "cross", "median_x", "ylo", "yhi")

    def __init__(self, depth):
        self.depth = depth
        self.cross = []       # перехресні ребра (quad-edge) знизу вгору
        self.median_x = None  # x вертикальної лінії медіани цього поділу
        self.ylo = None       # межі y зрізу (для малювання лінії медіани)
        self.yhi = None


class ChainRecorder:
    """Фіксує перехресні ребра кожного злиття під час ``delaunay._build``."""

    def __init__(self, cache):
        self.cache = cache
        self.chains = []

    def start_merge(self, depth, basel, median_x, ylo, yhi):
        ch = _Chain(depth)
        ch.cross.append(basel)          # нижній опорний відрізок (σ_out)
        ch.median_x, ch.ylo, ch.yhi = median_x, ylo, yhi
        self.chains.append(ch)
        return ch

    def cross(self, ch, basel):
        ch.cross.append(basel)          # чергова ланка (верхній стане σ_in)


def triangulate_with_chains(points):
    """Як ``delaunay.triangulate``, але додатково повертає ланцюги та кеш.

    Повертає (edges, uniq, recorder, cache).
    """
    pts = sorted(points, key=lambda p: (p.x, p.y))
    uniq = []
    for p in pts:
        if uniq and uniq[-1].x == p.x and uniq[-1].y == p.y:
            continue
        uniq.append(p)
    for i, p in enumerate(uniq):
        p.index = i

    cache = BisectorCache(uniq)
    rec = ChainRecorder(cache)
    if len(uniq) < 2:
        return [], uniq, rec, cache

    le, _ = delaunay._build(uniq, rec)
    return enumerate_edges(le), uniq, rec, cache


def _face_center(e, cache):
    """Центр кола лівої грані ребра e (вершина Вороного) або None (зовнішня)."""
    ring = []
    cur = e
    while True:
        ring.append(cur)
        cur = cur.lnext
        if cur is e:
            break
        if len(ring) > 3:
            return None  # зовнішня грань (довша за трикутник)
    if len(ring) == 3 and ccw(ring[0].org, ring[1].org, ring[2].org):
        return cache.vertex(ring[0].org.index, ring[1].org.index, ring[2].org.index)
    return None


def _dual_segment(e, cache, bbox, far):
    """Дуальне до ребра e ребро Вороного, відсічене до bbox (або None)."""
    xmin, ymin, xmax, ymax = bbox
    c1 = _face_center(e, cache)
    c2 = _face_center(e.sym, cache)
    if c1 is not None and c2 is not None:
        return clip_segment(c1, c2, xmin, ymin, xmax, ymax)
    if c1 is None and c2 is None:
        return None
    if c1 is not None:
        fe, c = e, c1
    else:
        fe, c = e.sym, c2
    dx = fe.dest.x - fe.org.x
    dy = fe.dest.y - fe.org.y
    nx, ny = dy, -dx                      # зовнішня нормаль (грань ліворуч)
    mag = math.hypot(nx, ny)
    if mag == 0:
        return None
    far_pt = (c[0] + nx / mag * far, c[1] + ny / mag * far)
    return clip_segment(c, far_pt, xmin, ymin, xmax, ymax)


def chain_drawables(recorder, cache, bbox):
    """Відрізки розділяючих ланцюгів = дуальні до перехресних ребер.

    Повертає (main_segs, other_segs, by_depth):
      main_segs  -- головний ланцюг (верхнє злиття, depth=0, що зшиває дві
                    половини всієї множини S);
      other_segs -- ланцюги всіх нижчих злиттів (одним списком);
      by_depth   -- {глибина рекурсії: [відрізки]} для розфарбування за
                    рівнями (наочно показує ієрархію «Розділяй та Пануй»).
    """
    far = 2.0 * ((bbox[2] - bbox[0]) + (bbox[3] - bbox[1])) + 1.0
    min_depth = min((ch.depth for ch in recorder.chains), default=0)

    main, other = [], []
    by_depth = {}
    for ch in recorder.chains:
        segs = []
        for e in ch.cross:
            seg = _dual_segment(e, cache, bbox, far)
            if seg:
                segs.append(seg)
        by_depth.setdefault(ch.depth, []).extend(segs)
        (main if ch.depth == min_depth else other).extend(segs)
    return main, other, by_depth


def median_lines(recorder, pad=0.0):
    """Вертикальні лінії медіан поділу кожного злиття.

    Повертає {глибина рекурсії: [((x, ylo), (x, yhi))]} — лінія медіани
    проходить вертикально через x = середина між двома центральними
    точками зрізу і охоплює діапазон y цього зрізу. ``pad`` подовжує лінію
    по вертикалі для наочності.
    """
    by_depth = {}
    for ch in recorder.chains:
        if ch.median_x is None:
            continue
        seg = ((ch.median_x, ch.ylo - pad), (ch.median_x, ch.yhi + pad))
        by_depth.setdefault(ch.depth, []).append(seg)
    return by_depth
