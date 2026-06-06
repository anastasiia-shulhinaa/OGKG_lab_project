"""Геометричні примітиви та предикати.

Координати точок зберігаються як ЦІЛІ числа. Завдяки арифметиці довгих
цілих у Python предикати ``ccw`` та ``in_circle`` обчислюються ТОЧНО
(без похибок float), що усуває вироджені «глюки» орієнтації навіть на
10^4 точок. Координати кола Вороного (``circumcenter``) — вже float,
бо потрібні лише для малювання.
"""

import math


class Point:
    """Точка площини з цілими координатами та власним індексом."""

    __slots__ = ("x", "y", "index")

    def __init__(self, x, y, index=-1):
        self.x = x
        self.y = y
        self.index = index

    def __repr__(self):
        return f"P{self.index}({self.x},{self.y})"


def ccw(a, b, c):
    """True, якщо трійка (a, b, c) утворює лівий поворот (проти годинника)."""
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x) > 0


def in_circle(a, b, c, d):
    """True, якщо d лежить СТРОГО всередині кола, описаного навколо
    трикутника (a, b, c), що заданий проти годинникової стрілки.

    Обчислюється через знак визначника 3x3 від різниць координат —
    точно, бо всі величини цілі.
    """
    ax, ay = a.x - d.x, a.y - d.y
    bx, by = b.x - d.x, b.y - d.y
    cx, cy = c.x - d.x, c.y - d.y
    det = (
        (ax * ax + ay * ay) * (bx * cy - cx * by)
        - (bx * bx + by * by) * (ax * cy - cx * ay)
        + (cx * cx + cy * cy) * (ax * by - bx * ay)
    )
    return det > 0


def circumcenter(a, b, c):
    """Центр описаного кола трикутника (a, b, c) — вершина Вороного.

    Повертає (x, y) як float або None для вироджених (колінеарних) трійок.
    """
    ax, ay = a.x, a.y
    bx, by = b.x, b.y
    cx, cy = c.x, c.y
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if d == 0:
        return None
    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return (ux, uy)


def clip_segment(p, q, xmin, ymin, xmax, ymax):
    """Відсікання відрізка [p, q] до прямокутника (алгоритм Лянга–Барскі).

    Повертає ((x0, y0), (x1, y1)) видимої частини або None.
    """
    x0, y0 = p
    x1, y1 = q
    dx = x1 - x0
    dy = y1 - y0
    t0, t1 = 0.0, 1.0
    checks = (
        (-dx, x0 - xmin),
        (dx, xmax - x0),
        (-dy, y0 - ymin),
        (dy, ymax - y0),
    )
    for pk, qk in checks:
        if pk == 0:
            if qk < 0:
                return None
        else:
            t = qk / pk
            if pk < 0:
                if t > t1:
                    return None
                if t > t0:
                    t0 = t
            else:
                if t < t0:
                    return None
                if t < t1:
                    t1 = t
    return ((x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy))
