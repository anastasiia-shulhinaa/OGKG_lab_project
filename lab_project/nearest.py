"""Пошук усіх найближчих сусідів через тріангуляцію Делоне.

Теорема: для кожної точки її найближчий сусід з'єднаний з нею ребром
Делоне. Тому достатньо для кожної вершини перебрати лише її сусідів у
тріангуляції — сумарно O(N), бо ребер у Делоне лінійно (<= 3N - 6).
"""


def all_nearest(edges, points):
    """Повертає (nn, pairs):
      nn[i]  -- індекс найближчого сусіда точки i (або None);
      pairs  -- список пар (Point_i, Point_nn[i]) для візуалізації.
    """
    n = len(points)
    nn = [None] * n
    nd = [None] * n  # квадрат відстані до поточного найближчого

    for e in edges:
        i = e.org.index
        q = e.dest
        p = points[i]
        d = (p.x - q.x) ** 2 + (p.y - q.y) ** 2
        if nd[i] is None or d < nd[i]:
            nd[i] = d
            nn[i] = q.index

    pairs = [(points[i], points[nn[i]]) for i in range(n) if nn[i] is not None]
    return nn, pairs
