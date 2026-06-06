"""Графічний інтерфейс демонстрації алгоритму «Розділяй та Пануй».

Задача: для множини S з N точок у E^2 знайти усіх найближчих сусідів за
O(N log N) через тріангуляцію Делоне (Гібас–Столфі) та дуальну до неї
діаграму Вороного.

Два режими вводу:
  * ручний  — клік мишею у робочій області (до 100 точок) для демонстрації;
  * випадковий — автоматична генерація до 10^4 точок для перевірки
    ефективності.
"""

import math
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib import cm
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure

from geometry import Point
from delaunay import triangulate
from voronoi import voronoi
from voronoi_chain import triangulate_with_chains, chain_drawables, median_lines
from nearest import all_nearest

W = 1000               # розмір робочої області (логічні координати 0..W)
MANUAL_LIMIT = 100     # макс. точок у ручному режимі
RANDOM_LIMIT = 10000   # макс. точок у випадковому режимі


class App:
    def __init__(self, root):
        self.root = root
        root.title("Найближчі сусіди — стратегія «Розділяй та Пануй» (Делоне/Вороной)")

        self.points = []          # список (x, y) — поточна множина S
        self.delaunay_segs = None # відрізки тріангуляції Делоне
        self.vor_segs = None      # відрізки діаграми Вороного
        self.nn_segs = None       # відрізки «точка -> найближчий сусід»
        self.chain_main = None    # головний розділяючий ланцюг (верхнє злиття)
        self.chain_other = None   # ланцюги нижчих злиттів
        self.chain_by_depth = None # {глибина: [відрізки]} для розфарбування
        self.median_by_depth = None # {глибина: [лінії медіан]}
        self._anim_job = None      # id запланованої анімації

        self._build_ui()
        self._redraw()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # ліворуч — робоча область (matplotlib)
        fig = Figure(figsize=(7, 7), dpi=100)
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self.root)
        self.canvas.get_tk_widget().pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("button_press_event", self._on_click)

        # праворуч — панель керування
        panel = ttk.Frame(self.root, padding=10)
        panel.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(panel, text="Режим вводу:", font=("", 10, "bold")).pack(anchor="w")
        self.mode = tk.StringVar(value="manual")
        ttk.Radiobutton(panel, text="Ручний (клік мишею, ≤100)",
                        variable=self.mode, value="manual").pack(anchor="w")
        ttk.Radiobutton(panel, text="Випадковий (≤10000)",
                        variable=self.mode, value="random").pack(anchor="w")

        gen = ttk.Frame(panel)
        gen.pack(anchor="w", pady=(6, 0), fill=tk.X)
        ttk.Label(gen, text="Кількість:").pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="1000")
        ttk.Entry(gen, textvariable=self.count_var, width=8).pack(side=tk.LEFT, padx=4)
        ttk.Button(gen, text="Згенерувати", command=self._generate).pack(side=tk.LEFT)

        ttk.Separator(panel, orient="horizontal").pack(fill=tk.X, pady=8)

        ttk.Button(panel, text="▶  Запустити алгоритм",
                   command=self._run).pack(fill=tk.X)
        ttk.Button(panel, text="🎬 Анімація розділяючого ланцюга",
                   command=self._animate_chain).pack(fill=tk.X, pady=(4, 0))
        ttk.Button(panel, text="Очистити робочу область",
                   command=self._clear).pack(fill=tk.X, pady=(4, 0))
        ttk.Button(panel, text="Бенчмарк (1k…10k)",
                   command=self._benchmark).pack(fill=tk.X, pady=(4, 0))

        ttk.Separator(panel, orient="horizontal").pack(fill=tk.X, pady=8)

        ttk.Label(panel, text="Шари відображення:", font=("", 10, "bold")).pack(anchor="w")
        self.show_points = tk.BooleanVar(value=True)
        self.show_delaunay = tk.BooleanVar(value=False)
        self.show_voronoi = tk.BooleanVar(value=True)
        self.show_nn = tk.BooleanVar(value=True)
        self.show_chain = tk.BooleanVar(value=True)
        self.show_all_chains = tk.BooleanVar(value=False)
        self.show_medians = tk.BooleanVar(value=True)
        for text, var in [
            ("Точки", self.show_points),
            ("Тріангуляція Делоне", self.show_delaunay),
            ("Діаграма Вороного", self.show_voronoi),
            ("Найближчі сусіди", self.show_nn),
            ("Розділяючий ланцюг (головне злиття)", self.show_chain),
            ("Усі ланцюги злиттів (рекурсія)", self.show_all_chains),
            ("Медіани (лінії поділу)", self.show_medians),
        ]:
            ttk.Checkbutton(panel, text=text, variable=var,
                            command=self._redraw).pack(anchor="w")

        ttk.Separator(panel, orient="horizontal").pack(fill=tk.X, pady=8)

        ttk.Label(panel, text="Журнал:", font=("", 10, "bold")).pack(anchor="w")
        self.log = tk.Text(panel, width=40, height=16, font=("Consolas", 9))
        self.log.pack(fill=tk.BOTH, expand=True)
        self._log("Готово. Додайте точки кліком або згенеруйте випадкові,\n"
                  "потім натисніть «Запустити алгоритм».")

    def _log(self, msg):
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)

    # -------------------------------------------------------------- події
    def _on_click(self, event):
        if self.mode.get() != "manual":
            return
        if event.inaxes != self.ax or event.xdata is None:
            return
        if len(self.points) >= MANUAL_LIMIT:
            messagebox.showinfo("Ліміт", f"Ручний режим: максимум {MANUAL_LIMIT} точок.")
            return
        x = int(round(event.xdata))
        y = int(round(event.ydata))
        if 0 <= x <= W and 0 <= y <= W:
            self.points.append((x, y))
            self._invalidate()
            self._redraw()

    def _generate(self):
        try:
            n = int(self.count_var.get())
        except ValueError:
            messagebox.showerror("Помилка", "Кількість має бути цілим числом.")
            return
        n = max(1, min(RANDOM_LIMIT, n))
        self.points = [(random.randint(0, W), random.randint(0, W)) for _ in range(n)]
        self._invalidate()
        self._redraw()
        self._log(f"Згенеровано {n} випадкових точок.")

    def _clear(self):
        self.points = []
        self._invalidate()
        self._redraw()
        self._log("Робочу область очищено.")

    def _invalidate(self):
        self.delaunay_segs = self.vor_segs = self.nn_segs = None
        self.chain_main = self.chain_other = self.chain_by_depth = None
        self.median_by_depth = None
        if self._anim_job is not None:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None

    # --------------------------------------------------------- алгоритм
    def _run(self):
        if len(self.points) < 2:
            messagebox.showinfo("Замало точок", "Потрібно щонайменше 2 точки.")
            return

        pts = [Point(x, y, i) for i, (x, y) in enumerate(self.points)]

        t0 = time.perf_counter()
        # Етап 1 + Етап 2 (Р та П) з фіксацією розділяючих ланцюгів Вороного
        edges, uniq, rec, cache = triangulate_with_chains(pts)
        t1 = time.perf_counter()
        self.vor_segs = voronoi(edges, (0, 0, W, W))
        self.chain_main, self.chain_other, self.chain_by_depth = \
            chain_drawables(rec, cache, (0, 0, W, W))
        self.median_by_depth = median_lines(rec)
        nn, pairs = all_nearest(edges, uniq)    # усі найближчі сусіди
        t2 = time.perf_counter()

        # відрізки Делоне (без дублів)
        segs, seen = [], set()
        for e in edges:
            k, ks = id(e), id(e.sym)
            key = (k, ks) if k < ks else (ks, k)
            if key in seen:
                continue
            seen.add(key)
            segs.append(((e.org.x, e.org.y), (e.dest.x, e.dest.y)))
        self.delaunay_segs = segs
        self.nn_segs = [((p.x, p.y), (q.x, q.y)) for p, q in pairs]

        n = len(uniq)
        build_ms = (t1 - t0) * 1000
        total_ms = (t2 - t0) * 1000
        ratio = (t1 - t0) / (n * math.log2(n)) * 1e6 if n > 1 else 0.0
        self._log("─" * 34)
        self._log(f"N = {n} унікальних точок")
        self._log(f"Тріангуляція Делоне : {build_ms:8.1f} мс")
        self._log(f"Вороной + сусіди    : {(total_ms - build_ms):8.1f} мс")
        self._log(f"Разом               : {total_ms:8.1f} мс")
        self._log(f"Ребер Делоне={len(segs)}  ребер Вороного={len(self.vor_segs)}")
        self._log(f"t/(N·log₂N) = {ratio:.3f} мкс  →  O(N log N)")
        vh, vm = cache.vert_hits, cache.vert_miss
        hr = 100 * vh / max(1, vh + vm)
        self._log(f"Кеш бісектрис: {vh} влучань / {vm} промахів ({hr:.0f}% reuse)")
        self._log(f"Головний ланцюг: {len(self.chain_main)} ланок "
                  f"(злиттів усього: {len(rec.chains)})")
        m_split = n // 2
        self._log(f"Поділ по медіані (верхнє злиття): "
                  f"ліворуч {m_split} / праворуч {n - m_split} точок")
        self._redraw()

    def _benchmark(self):
        self._log("═" * 34)
        self._log("Бенчмарк (лише тріангуляція Делоне):")
        self._log(f"{'N':>6} {'час, мс':>10} {'t/(N·log₂N), мкс':>18}")
        for n in (1000, 2000, 4000, 8000, 10000):
            pts = [Point(random.randint(0, 10 ** 6), random.randint(0, 10 ** 6), i)
                   for i in range(n)]
            t0 = time.perf_counter()
            triangulate(pts)
            dt = time.perf_counter() - t0
            self._log(f"{n:>6} {dt * 1000:>10.1f} {dt / (n * math.log2(n)) * 1e6:>18.3f}")
            self.root.update_idletasks()
        self._log("Сталий стовпчик t/(N·log₂N) ⇒ емпірично O(N log N).")

    def _animate_chain(self):
        """Поетапно малює головний розділяючий ланцюг (σ_out → σ_in)."""
        if self.chain_main is None:
            self._run()
        if not self.chain_main:
            messagebox.showinfo("Ланцюг", "Немає головного ланцюга для анімації "
                                          "(замало точок).")
            return
        if self._anim_job is not None:
            self.root.after_cancel(self._anim_job)
            self._anim_job = None

        segs = self.chain_main
        ax = self.ax
        ax.clear()
        ax.set_xlim(0, W)
        ax.set_ylim(0, W)
        ax.set_aspect("equal")
        ax.set_title("Анімація розділяючого ланцюга: σ_out → зигзаг → σ_in")
        if self.vor_segs:
            ax.add_collection(LineCollection(self.vor_segs, colors="#dddddd",
                                             linewidths=0.6))
        if self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            ax.scatter(xs, ys, s=12 if len(xs) <= 2000 else 3,
                       color="black", zorder=5)
        coll = LineCollection([], colors="#2ca02c", linewidths=2.4, zorder=6)
        ax.add_collection(coll)
        self.canvas.draw_idle()

        total = len(segs)
        step_ms = max(15, min(120, 3000 // max(1, total)))

        def step(k):
            coll.set_segments(segs[:k])
            self.canvas.draw_idle()
            if k < total:
                self._anim_job = self.root.after(step_ms, step, k + 1)
            else:
                self._anim_job = None

        step(1)

    # ------------------------------------------------------------ малювання
    def _redraw(self):
        ax = self.ax
        ax.clear()
        ax.set_xlim(0, W)
        ax.set_ylim(0, W)
        ax.set_aspect("equal")
        ax.set_title(f"S: {len(self.points)} точок  "
                     f"(режим: {'ручний' if self.mode.get() == 'manual' else 'випадковий'})")

        if self.show_voronoi.get() and self.vor_segs:
            ax.add_collection(LineCollection(self.vor_segs, colors="#1f77b4",
                                             linewidths=0.7))
        if self.show_delaunay.get() and self.delaunay_segs:
            ax.add_collection(LineCollection(self.delaunay_segs, colors="#cccccc",
                                             linewidths=0.5))
        if self.show_medians.get() and self.median_by_depth:
            # вертикальні лінії медіан поділу (пунктир), колір = глибина рекурсії
            depths = sorted(self.median_by_depth)
            denom = max(1, len(depths) - 1)
            for k, d in enumerate(depths):
                color = cm.viridis(k / denom)
                lw = 1.8 if k == 0 else 0.8
                ax.add_collection(LineCollection(self.median_by_depth[d],
                                                 colors=[color], linewidths=lw,
                                                 linestyles="dashed", zorder=3))
        if self.show_all_chains.get() and self.chain_by_depth:
            # розфарбування ланцюгів за глибиною рекурсії (ієрархія Р та П):
            # неглибокі злиття (довгі ланцюги) -> фіолетовий, глибокі -> жовтий
            depths = sorted(self.chain_by_depth)
            denom = max(1, len(depths) - 1)
            for k, d in enumerate(depths):
                color = cm.viridis(k / denom)
                ax.add_collection(LineCollection(self.chain_by_depth[d],
                                                 colors=[color], linewidths=1.0))
        if self.show_chain.get() and self.chain_main:
            ax.add_collection(LineCollection(self.chain_main, colors="#2ca02c",
                                             linewidths=2.2, zorder=4))
        if self.show_nn.get() and self.nn_segs:
            ax.add_collection(LineCollection(self.nn_segs, colors="#d62728",
                                             linewidths=1.0))
        if self.show_points.get() and self.points:
            xs = [p[0] for p in self.points]
            ys = [p[1] for p in self.points]
            s = 12 if len(xs) <= 2000 else 3
            ax.scatter(xs, ys, s=s, color="black", zorder=5)

        self.canvas.draw_idle()


def main():
    root = tk.Tk()
    App(root)
    root.geometry("1180x780")
    root.mainloop()


if __name__ == "__main__":
    main()
