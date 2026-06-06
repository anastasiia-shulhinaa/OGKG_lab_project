"""Побудова діаграми Вороного як дуала тріангуляції Делоне.

Кожна трикутна грань Делоне -> одна вершина Вороного (центр описаного
кола). Спільне ребро двох трикутників -> відрізок Вороного між їхніми
центрами. Ребро на опуклій оболонці -> промінь Вороного, що йде назовні
по серединному перпендикуляру (відсікається до робочої області).
"""

import math

from geometry import ccw, circumcenter, clip_segment


def _faces(edges):
    """Призначити кожному напрямленому ребру його ЛІВУ грань та центр кола.

    Повертає (edge_face, face_circum):
      edge_face[id(e)]   -> номер грані;
      face_circum[грань] -> (x, y) центру кола або None (зовнішня грань).
    """
    edge_face = {}
    face_circum = []
    fid = 0
    for e in edges:
        if id(e) in edge_face:
            continue
        ring = []
        cur = e
        while True:
            ring.append(cur)
            edge_face[id(cur)] = fid
            cur = cur.lnext
            if cur is e:
                break
        if len(ring) == 3 and ccw(ring[0].org, ring[1].org, ring[2].org):
            face_circum.append(circumcenter(ring[0].org, ring[1].org, ring[2].org))
        else:
            face_circum.append(None)  # зовнішня (нескінченна) грань
        fid += 1
    return edge_face, face_circum


def voronoi(edges, bbox):
    """Список відрізків діаграми Вороного, відсічених до bbox.

    bbox = (xmin, ymin, xmax, ymax).
    Повертає список ((x0, y0), (x1, y1)).
    """
    edge_face, face_circum = _faces(edges)
    xmin, ymin, xmax, ymax = bbox
    far_len = 2.0 * ((xmax - xmin) + (ymax - ymin)) + 1.0

    segments = []
    seen = set()
    for e in edges:
        k, ks = id(e), id(e.sym)
        key = (k, ks) if k < ks else (ks, k)
        if key in seen:
            continue
        seen.add(key)

        c1 = face_circum[edge_face[id(e)]]
        c2 = face_circum[edge_face[id(e.sym)]]

        if c1 is not None and c2 is not None:
            s = clip_segment(c1, c2, xmin, ymin, xmax, ymax)
            if s:
                segments.append(s)
        elif c1 is None and c2 is None:
            continue  # вироджений випадок (усі точки колінеарні)
        else:
            # ребро оболонки -> промінь від центра кола назовні
            if c1 is not None:
                fe, c = e, c1
            else:
                fe, c = e.sym, c2
            # внутрішня грань ліворуч від fe => зовнішня нормаль праворуч
            dx = fe.dest.x - fe.org.x
            dy = fe.dest.y - fe.org.y
            nx, ny = dy, -dx
            mag = math.hypot(nx, ny)
            if mag == 0:
                continue
            far = (c[0] + nx / mag * far_len, c[1] + ny / mag * far_len)
            s = clip_segment(c, far, xmin, ymin, xmax, ymax)
            if s:
                segments.append(s)

    return segments
