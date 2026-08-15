"""Побудова графіка BLEU vs BERTScore F1 по типах тексту.

Навіщо цей графік. Markdown-таблиця в README дає точні числа, але не показує
головного: поверхнева метрика (BLEU) і семантична (BERTScore F1) розходяться
залежно від типу тексту. BLEU гуляє в діапазоні 19.50-49.81 — розкид у 2.5
раза, — тоді як BERTScore тримається в межах 90.70-94.11, тобто 3.4 пункти.
Іншими словами: там, де BLEU повідомляє про «поганий» переклад, семантична
близькість лишається високою. Це форма, а не числа, і таблиця її не передає.

Чому scatter, а не стовпчики з двома осями. Дві осі з непорівнянними шкалами
дозволяють підігнати картинку під будь-який висновок: досить розтягнути одну
шкалу, і «розрив» між метриками з'явиться або зникне. Scatter показує пари
значень чесно — кожна точка стоїть там, де стоїть.

Джерело чисел: README.md, розділ «Metrics by text type» (він же
«Метрики по типах тексту» в README.uk.md). Метрики тут НЕ перераховуються —
за їх обчислення відповідає src/validate.py. Якщо таблиця в README колись
зміниться, METRICS нижче треба оновити разом з нею.

Запуск:
    python scripts/plot_metrics.py

Потребує matplotlib (не входить у requirements.txt: це інструмент для
документації, а не частина пайплайну):
    pip install -r requirements-dev.txt
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

# Agg — незалежний від дисплея бекенд. Без нього результат залежав би від
# наявності GUI-тулкіта на машині, а графік має будуватися і в headless CI.
matplotlib.use("Agg")

import matplotlib.pyplot as plt

# (тип тексту, BLEU, BERTScore F1). n не використовується для розміру точки:
# кодувати його площею без легенди — означає показати вимір, який читач не
# зможе розшифрувати.
METRICS: list[tuple[str, float, float]] = [
    ("dialogue", 23.26, 92.15),
    ("ui_short", 22.76, 90.70),
    ("narrative", 23.81, 92.75),
    ("mechanic_description", 19.50, 90.92),
    ("book_or_document", 21.61, 91.41),
    ("telepathic", 39.72, 93.46),
    ("ui_keybind", 49.81, 94.11),
]

# Зміщення підпису відносно точки, у пунктах, та горизонтальне вирівнювання.
# Задані вручну і зафіксовані: п'ять із семи типів злипаються в кут
# BLEU 19-24, і будь-яке автоматичне розкладання підписів або накладало б їх,
# або залежало б від версії matplotlib. Фіксований layout — вимога
# відтворюваності.
LABEL_OFFSETS: dict[str, tuple[float, float, str]] = {
    "narrative": (7, 5, "left"),
    "dialogue": (7, -3, "left"),
    # Обидва найдовші підписи йдуть управо: вліво вони не вміщаються між
    # точкою і віссю Y і налазять на її заголовок.
    "book_or_document": (8, 6, "left"),
    "mechanic_description": (8, 8, "left"),
    "ui_short": (7, -10, "left"),
    "telepathic": (0, 10, "center"),
    "ui_keybind": (0, 10, "center"),
}

# Межі осей. Бриф пропонував приблизно 0-50 і 80-100, але на реальних числах
# такі межі притискають усі сім точок у нижню смугу: по Y дані займали б лише
# 17% висоти. Тут межі підтягнуті до даних із запасом на підписи, щоб розкид
# займав площу — саме це бриф і ставив за мету.
XLIM = (15.0, 55.0)
YLIM = (90.0, 95.0)

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "metrics_bleu_vs_bertscore.png"


def build_figure() -> plt.Figure:
    """Зібрати фігуру. Чиста побудова, без запису на диск."""
    fig, ax = plt.subplots(figsize=(8.0, 5.0), dpi=200)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    xs = [bleu for _, bleu, _ in METRICS]
    ys = [bert for _, _, bert in METRICS]
    ax.scatter(xs, ys, s=90, color="#2b6cb0", edgecolors="white", linewidths=1.2, zorder=3)

    for name, bleu, bert in METRICS:
        dx, dy, ha = LABEL_OFFSETS[name]
        ax.annotate(
            name,
            xy=(bleu, bert),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=9,
            color="#1a202c",
        )

    ax.set_xlim(*XLIM)
    ax.set_ylim(*YLIM)
    ax.set_xlabel("BLEU (surface n-gram overlap) — higher is better", fontsize=10)
    ax.set_ylabel("BERTScore F1 (semantic similarity) — higher is better", fontsize=10)
    ax.set_title(
        "Surface and semantic metrics diverge by text type\nBG3 EN-UK corpus, Gemini translation of a 4,992-pair sample",
        fontsize=11,
    )

    ax.grid(True, linestyle=":", linewidth=0.6, color="#cbd5e0", zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    fig.tight_layout()
    return fig


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure()
    # metadata={"Software": None} прибирає з PNG тег із версією matplotlib.
    # Без цього два запуски на різних версіях давали б різні байти, і перевірка
    # відтворюваності перетворилася б на перевірку версії бібліотеки.
    fig.savefig(OUTPUT, format="png", facecolor="white", metadata={"Software": None})
    plt.close(fig)
    print(f"written: {OUTPUT}")


if __name__ == "__main__":
    main()
