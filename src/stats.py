"""
stats.py — описова статистика корпусу для Розділу 4.

Читає: data/corpus.jsonl
Пише:  data/stats.md

Розділи:
  1. Загальна кількість пар
  2. Розподіл за 7 класами
  3. Розподіл length_class
  4. Статистика токенів EN / uk_human / uk_gemini
  5. Теги: скільки записів з кожним типом тегу
  6. Tag asymmetry
  7. Вибірка Gemini
"""

import json
import re
import statistics
from collections import Counter
from pathlib import Path

CORPUS_PATH = Path("data/corpus.jsonl")
STATS_PATH  = Path("data/stats.md")

# Простий whitespace-токенізатор (достатньо для порівняльної статистики)
def tokenize(text: str) -> list[str]:
    return text.split()


def percentile(data: list[float], p: float) -> float:
    data_s = sorted(data)
    idx = int(len(data_s) * p / 100)
    idx = min(idx, len(data_s) - 1)
    return data_s[idx]


def tok_stats(counts: list[int]) -> dict:
    return {
        "mean":   round(statistics.mean(counts), 1),
        "median": statistics.median(counts),
        "p95":    percentile(counts, 95),
        "min":    min(counts),
        "max":    max(counts),
    }


def run(corpus_path: Path = CORPUS_PATH, out_path: Path = STATS_PATH) -> None:
    records = []
    with corpus_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    sample = [r for r in records if r["metadata"].get("in_sample")]
    n_sample = len(sample)
    n_with_gemini = sum(1 for r in records if r.get("uk_gemini") is not None)

    # ── Розподіл за класами ──────────────────────────────────────────────────
    type_counts = Counter(r["metadata"]["type"] for r in records)
    type_order  = [t for t, _ in type_counts.most_common()]

    # ── Розподіл length_class ────────────────────────────────────────────────
    lc_counts = Counter(r["metadata"]["length_class"] for r in records)

    # ── Токени ───────────────────────────────────────────────────────────────
    en_toks  = [len(tokenize(r["en"]))       for r in records]
    ukh_toks = [len(tokenize(r["uk_human"])) for r in records]
    ukg_toks = [len(tokenize(r["uk_gemini"])) for r in sample if r.get("uk_gemini")]

    en_stats  = tok_stats(en_toks)
    ukh_stats = tok_stats(ukh_toks)
    ukg_stats = tok_stats(ukg_toks)

    # ── Теги ─────────────────────────────────────────────────────────────────
    has_lstag  = sum(1 for r in records if r["metadata"].get("has_lstag"))
    has_italic = sum(1 for r in records if r["metadata"].get("has_italic"))
    has_bold   = sum(1 for r in records if r["metadata"].get("has_bold"))
    has_br     = sum(1 for r in records if r["metadata"].get("has_br"))
    has_ph     = sum(1 for r in records if r["metadata"].get("has_placeholder"))

    # ── Tag asymmetry ─────────────────────────────────────────────────────────
    asym_true  = sum(1 for r in records if r["metadata"].get("tag_asymmetry"))
    asym_false = total - asym_true

    # Асиметрія по класах
    asym_by_type: dict[str, list[int]] = {}
    for r in records:
        t = r["metadata"]["type"]
        asym_by_type.setdefault(t, [0, 0])
        asym_by_type[t][1] += 1
        if r["metadata"].get("tag_asymmetry"):
            asym_by_type[t][0] += 1

    # ── Duplicate_count ──────────────────────────────────────────────────────
    dup_counts = [r["metadata"].get("duplicate_count", 1) for r in records]
    total_original_pairs = sum(dup_counts)

    # ── Будуємо Markdown ─────────────────────────────────────────────────────
    lines = []
    a = lines.append

    a("# Статистика корпусу BG3-EN-UK\n")
    a(f"*Згенеровано автоматично з `data/corpus.jsonl`*\n")
    a("")

    # 1. Загальне
    a("## 1. Загальна кількість пар\n")
    a(f"| Метрика | Значення |")
    a(f"|---------|---------|")
    a(f"| Всього пар у corpus.jsonl | **{total:,}** |")
    a(f"| Унікальних пар (з урахуванням дублікатів) | {total:,} |")
    a(f"| Оригінальних пар до дедуплікації | {total_original_pairs:,} |")
    a(f"| Видалено дублікатів | {total_original_pairs - total:,} |")
    a(f"| Записів у вибірці (in_sample=true) | {n_sample:,} |")
    a(f"| Записів з uk_gemini (переклад Gemini) | {n_with_gemini:,} |")
    a(f"| Записів лише з uk_human (поза вибіркою) | {total - n_with_gemini:,} |")
    a("")

    # 2. Розподіл за класами
    a("## 2. Розподіл за типами тексту\n")
    a(f"| Тип | Записів | % від корпусу | У вибірці |")
    a(f"|-----|---------|--------------|-----------|")
    sample_by_type = Counter(r["metadata"]["type"] for r in sample)
    for t in type_order:
        cnt = type_counts[t]
        sc  = sample_by_type.get(t, 0)
        a(f"| `{t}` | {cnt:,} | {cnt/total*100:.1f}% | {sc:,} |")
    a(f"| **Разом** | **{total:,}** | 100% | **{n_sample:,}** |")
    a("")

    # 3. Length class
    a("## 3. Розподіл за довжиною (length_class)\n")
    a(f"| Клас | Діапазон EN (символів) | Записів | % |")
    a(f"|------|----------------------|---------|---|")
    lc_defs = [
        ("short",   "< 100"),
        ("medium",  "100–499"),
        ("long",    "500–2000"),
        ("extreme", "> 2000"),
    ]
    for lc, rng in lc_defs:
        cnt = lc_counts.get(lc, 0)
        a(f"| `{lc}` | {rng} | {cnt:,} | {cnt/total*100:.1f}% |")
    a("")

    # 4. Токени
    a("## 4. Статистика токенів (whitespace tokenization)\n")
    a(f"| Колонка | Середнє | Медіана | P95 | Мін | Макс |")
    a(f"|---------|---------|---------|-----|-----|------|")
    a(f"| EN | {en_stats['mean']} | {en_stats['median']} | {en_stats['p95']} | {en_stats['min']} | {en_stats['max']} |")
    a(f"| uk_human | {ukh_stats['mean']} | {ukh_stats['median']} | {ukh_stats['p95']} | {ukh_stats['min']} | {ukh_stats['max']} |")
    a(f"| uk_gemini *(вибірка, n={n_with_gemini:,})* | {ukg_stats['mean']} | {ukg_stats['median']} | {ukg_stats['p95']} | {ukg_stats['min']} | {ukg_stats['max']} |")
    a("")
    a(f"> Токенізація: розбиття по пробілах (whitespace split). "
      f"Для точних BPE-підрахунків використовуйте `validate.py`.")
    a("")

    # 5. Теги
    a("## 5. Наявність тегів і форматування\n")
    a(f"| Маркер | Записів | % корпусу |")
    a(f"|--------|---------|-----------|")
    a(f"| `<LSTag>` (інтерактивна підказка) | {has_lstag:,} | {has_lstag/total*100:.1f}% |")
    a(f"| `<i>` (курсив / внутрішній голос) | {has_italic:,} | {has_italic/total*100:.1f}% |")
    a(f"| `<b>` (жирний) | {has_bold:,} | {has_bold/total*100:.1f}% |")
    a(f"| `<br>` (перенос рядка) | {has_br:,} | {has_br/total*100:.1f}% |")
    a(f"| `[N]` (плейсхолдер) | {has_ph:,} | {has_ph/total*100:.1f}% |")
    a("")

    # 6. Tag asymmetry
    a("## 6. Tag asymmetry (різна кількість тегів EN vs UK)\n")
    a(f"| Статус | Записів | % |")
    a(f"|--------|---------|---|")
    a(f"| tag_asymmetry = false | {asym_false:,} | {asym_false/total*100:.1f}% |")
    a(f"| tag_asymmetry = true  | {asym_true:,} | {asym_true/total*100:.1f}% |")
    a("")
    a(f"### По класах\n")
    a(f"| Тип | Асиметрія | Всього | % |")
    a(f"|-----|-----------|--------|---|")
    for t in type_order:
        a_cnt, t_cnt = asym_by_type.get(t, [0, 0])
        pct = a_cnt / t_cnt * 100 if t_cnt else 0
        a(f"| `{t}` | {a_cnt:,} | {t_cnt:,} | {pct:.1f}% |")
    a("")

    # 7. Вибірка
    a("## 7. Стратифікована вибірка для Gemini\n")
    a(f"| Метрика | Значення |")
    a(f"|---------|---------|")
    a(f"| Розмір вибірки | {n_sample:,} |")
    a(f"| Seed | 42 |")
    a(f"| Перекладено Gemini | {n_with_gemini:,} (100%) |")
    a(f"| Модель | gemini-3.1-flash-lite |")
    a(f"| Temperature | 0.2 |")
    a("")
    a(f"### Розподіл вибірки за класами\n")
    a(f"| Тип | У вибірці | % вибірки | % від класу |")
    a(f"|-----|-----------|-----------|------------|")
    for t in type_order:
        sc   = sample_by_type.get(t, 0)
        tc   = type_counts[t]
        a(f"| `{t}` | {sc:,} | {sc/n_sample*100:.1f}% | {sc/tc*100:.1f}% |")
    a("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Збережено: {out_path}")


if __name__ == "__main__":
    run()
