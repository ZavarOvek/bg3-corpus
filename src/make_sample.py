"""
make_sample.py — стратифікована вибірка ~5000 записів для Gemini.

Пропорції (seed=42):
  dialogue            2500
  ui_short             700
  narrative            800
  mechanic_description 600
  book_or_document     200
  telepathic           100
  ui_keybind            92  (усі)

Виходи:
  data/intermediate/sample.jsonl   — вибрані записи
  data/intermediate/filtered.jsonl — оновлений: додано "in_sample": true/false
"""

import json
import random
from pathlib import Path

INTERMEDIATE = Path("data/intermediate")
random.seed(42)

STRATA: dict[str, int] = {
    "dialogue":             2500,
    "ui_short":              700,
    "narrative":             800,
    "mechanic_description":  600,
    "book_or_document":      200,
    "telepathic":            100,
    "ui_keybind":             92,  # усі — в filtered їх рівно 92
}


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_jsonl(records: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


records = load_jsonl(INTERMEDIATE / "filtered.jsonl")

# Групуємо по класах
by_class: dict[str, list[dict]] = {}
for rec in records:
    cls = rec["metadata"]["type"]
    by_class.setdefault(cls, []).append(rec)

# Семплінг
sample_ids: set[str] = set()
sample_records: list[dict] = []

for cls, n in STRATA.items():
    pool = by_class.get(cls, [])
    chosen = random.sample(pool, min(n, len(pool)))
    for rec in chosen:
        sample_ids.add(rec["id"])
    sample_records.extend(chosen)
    print(f"  {cls:<25} {len(chosen):>4} / {len(pool):>6}  запитано={n}")

print(f"\nВсього у вибірці: {len(sample_records)}")

# Зберігаємо sample.jsonl
save_jsonl(sample_records, INTERMEDIATE / "sample.jsonl")
print(f"Збережено: {INTERMEDIATE / 'sample.jsonl'}")

# Оновлюємо filtered.jsonl: додаємо in_sample
updated = []
for rec in records:
    rec["in_sample"] = rec["id"] in sample_ids
    updated.append(rec)

save_jsonl(updated, INTERMEDIATE / "filtered.jsonl")
print(f"Оновлено:  {INTERMEDIATE / 'filtered.jsonl'} (in_sample прапор)")

# Перевірка
in_sample_count = sum(1 for r in updated if r["in_sample"])
print(f"\nПерехресна перевірка: in_sample=True у filtered.jsonl: {in_sample_count}")
