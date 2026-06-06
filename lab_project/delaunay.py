"""Тріангуляція Делоне методом «Розділяй та Пануй» (Гібас–Столфі).

Це і є реалізація стратегії «Р та П» із завдання, але у ДУАЛЬНОМУ
просторі (Делоне), що набагато стійкіше, ніж пряме зшивання комірок
Вороного, і дає ту саму складність O(N log N):

  Етап 1 (спуск). Точки сортуються за X та рекурсивно діляться навпіл
  по медіані X на ліву (L) та праву (R) підмножини. База рекурсії —
  2 точки (одне ребро) або 3 точки (трикутник або відрізок).

  Етап 2 (підйом). Дві сусідні тріангуляції зшиваються: знаходиться
  НИЖНІЙ опорний відрізок (нижня спільна дотична) і знизу вгору
  «зигзагом» додаються перехресні ребра basel, а ребра, що порушують
  умову Делоне, вилучаються. Ця висхідна дотична — точний дуал
  розділяючого ланцюга Вороного з опису завдання.
"""

import sys

from geometry import ccw, in_circle
from quadedge import make_edge, splice, connect, delete_edge, enumerate_edges

# глибина рекурсії ~ log2(N); із запасом для 10^4 точок
sys.setrecursionlimit(100000)


def _right_of(p, e):
    return ccw(p, e.dest, e.org)


def _left_of(p, e):
    return ccw(p, e.org, e.dest)


def _build(S):
    """Рекурсивно побудувати тріангуляцію відсортованого зрізу S.

    Повертає пару (ldo, rdo): крайнє ліве (вихідне з найлівішої точки)
    та крайнє праве ребра опуклої оболонки фрагмента.
    """
    n = len(S)

    if n == 2:
        a = make_edge(S[0], S[1])
        return a, a.sym

    if n == 3:
        a = make_edge(S[0], S[1])
        b = make_edge(S[1], S[2])
        splice(a.sym, b)
        if ccw(S[0], S[1], S[2]):
            connect(b, a)
            return a, b.sym
        elif ccw(S[0], S[2], S[1]):
            c = connect(b, a)
            return c.sym, c
        else:  # три колінеарні точки -> просто ланцюжок
            return a, b.sym

    # --- Етап 1: поділ по медіані X ---
    m = n // 2
    ldo, ldi = _build(S[:m])
    rdi, rdo = _build(S[m:])

    # --- Етап 2: пошук нижньої спільної дотичної ---
    while True:
        if _left_of(rdi.org, ldi):
            ldi = ldi.lnext
        elif _right_of(ldi.org, rdi):
            rdi = rdi.rprev
        else:
            break

    # перше зшиваюче ребро (нижній опорний відрізок)
    basel = connect(rdi.sym, ldi)
    if ldi.org is ldo.org:
        ldo = basel.sym
    if rdi.org is rdo.org:
        rdo = basel

    # --- зигзагоподібне зшивання знизу вгору ---
    while True:
        lcand = basel.sym.onext
        if _right_of(lcand.dest, basel):
            while in_circle(basel.dest, basel.org, lcand.dest, lcand.onext.dest):
                t = lcand.onext
                delete_edge(lcand)
                lcand = t

        rcand = basel.oprev
        if _right_of(rcand.dest, basel):
            while in_circle(basel.dest, basel.org, rcand.dest, rcand.oprev.dest):
                t = rcand.oprev
                delete_edge(rcand)
                rcand = t

        l_valid = _right_of(lcand.dest, basel)
        r_valid = _right_of(rcand.dest, basel)
        if not l_valid and not r_valid:
            break  # дійшли до верхнього опорного відрізка — кінець

        if (not l_valid) or (
            r_valid and in_circle(lcand.dest, lcand.org, rcand.org, rcand.dest)
        ):
            basel = connect(rcand, basel.sym)
        else:
            basel = connect(basel.sym, lcand.sym)

    return ldo, rdo


def triangulate(points):
    """Побудувати тріангуляцію Делоне множини точок.

    points -- список об'єктів Point.
    Повертає (edges, uniq):
      edges -- усі напрямлені ребра quad-edge структури;
      uniq  -- відсортований список унікальних точок із переіндексацією
               (point.index == позиція у uniq), на нього спираються
               діаграма Вороного та пошук сусідів.
    """
    pts = sorted(points, key=lambda p: (p.x, p.y))

    uniq = []
    for p in pts:
        if uniq and uniq[-1].x == p.x and uniq[-1].y == p.y:
            continue
        uniq.append(p)
    for i, p in enumerate(uniq):
        p.index = i

    if len(uniq) < 2:
        return [], uniq

    le, _ = _build(uniq)
    return enumerate_edges(le), uniq
