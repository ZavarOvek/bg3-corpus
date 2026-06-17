"""
filter.py — очищення і збагачення metadata для classified.jsonl.

Операції:
  1. Стрип хвостових <br> і whitespace (EN і UK)
  2. Видалення записів де EN або UK стали порожніми після стрипу
  3. Дедуплікація по парі (en, uk_human) після стрипу
  4. Обрахунок metadata прапорів

Теги в ТІЛІ тексту — не чіпаємо.

Читає: data/intermediate/classified.jsonl
Пише:  data/intermediate/filtered.jsonl
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

INTERMEDIATE = Path("data/intermediate")

# Всі варіанти <br> в хвості (один або кілька)
TAIL_BR_RE = re.compile(r"(\s*<br\s*/?>)+\s*$", re.IGNORECASE)

# Для підрахунку тегів у тілі (після стрипу хвоста)
LSTAG_COUNT_RE = re.compile(r"<LSTag[^>]*/?>|</LSTag>", re.IGNORECASE)
ITAG_COUNT_RE  = re.compile(r"</?i>", re.IGNORECASE)
BTAG_COUNT_RE  = re.compile(r"</?b>", re.IGNORECASE)
BRTAG_COUNT_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)

# Плейсхолдери: [1], [2], [UUID-подібне]
PLACEHOLDER_RE = re.compile(r"\[\d+\]|\[[0-9a-f]{8}-[0-9a-f-]{27,}\]", re.IGNORECASE)


def strip_tail(text: str) -> str:
    """Видаляє хвостові <br> (всі варіанти) і whitespace."""
    text = TAIL_BR_RE.sub("", text)
    return text.rstrip()


def length_class(n: int) -> str:
    if n < 100:
        return "short"
    if n < 500:
        return "medium"
    if n <= 2000:
        return "long"
    return "extreme"


def tag_counts(text: str) -> dict[str, int]:
    return {
        "LSTag": len(LSTAG_COUNT_RE.findall(text)),
        "i":     len(ITAG_COUNT_RE.findall(text)),
        "b":     len(BTAG_COUNT_RE.findall(text)),
        "br":    len(BRTAG_COUNT_RE.findall(text)),
    }


def build_metadata(rec: dict, en_clean: str, uk_clean: str) -> dict:
    """Будує повний metadata-словник для одного запису."""
    en_tags = tag_counts(en_clean)
    uk_tags = tag_counts(uk_clean)

    asymmetry_details: dict[str, list[int]] = {}
    for tag in ("LSTag", "i", "b", "br"):
        if en_tags[tag] != uk_tags[tag]:
            asymmetry_details[tag] = [en_tags[tag], uk_tags[tag]]

    char_en = len(en_clean)
    char_uk = len(uk_clean)

    existing = rec.get("metadata", {})
    return {
        "type":                existing.get("type", "other"),
        "length_class":        length_class(char_en),
        "char_count_en":       char_en,
        "char_count_uk":       char_uk,
        "has_lstag":           en_tags["LSTag"] > 0,
        "has_italic":          en_tags["i"] > 0,
        "has_bold":            en_tags["b"] > 0,
        "has_br":              en_tags["br"] > 0,
        "has_placeholder":     bool(PLACEHOLDER_RE.search(en_clean)),
        "tag_asymmetry":       bool(asymmetry_details),
        "tag_asymmetry_details": asymmetry_details if asymmetry_details else None,
        "uk_human_quality":    existing.get("uk_human_quality", "clean"),
        "duplicate_count":     1,  # буде оновлено при дедуплікації
    }


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(in_path: Path, out_path: Path) -> list[dict]:
    records = load_jsonl(in_path)
    total_in = len(records)

    # ── Крок 1: стрип хвостів ────────────────────────────────────────────────
    stripped: list[dict] = []
    empty_count = 0

    for rec in records:
        en_clean  = strip_tail(rec["en"])
        uk_clean  = strip_tail(rec["uk_human"])

        if not en_clean or not uk_clean:
            empty_count += 1
            continue

        stripped.append({
            "id":       rec["id"],
            "version":  rec["version"],
            "en":       en_clean,
            "uk_human": uk_clean,
            "metadata": rec.get("metadata", {}),
        })

    # ── Крок 2: дедуплікація по (en, uk_human) ───────────────────────────────
    seen: dict[tuple[str, str], int] = {}   # (en, uk) → індекс у deduped
    deduped: list[dict] = []
    dup_removed = 0

    for rec in stripped:
        key = (rec["en"], rec["uk_human"])
        if key in seen:
            # Збільшуємо лічильник у першому екземплярі
            deduped[seen[key]]["_dup_count"] += 1
            dup_removed += 1
        else:
            seen[key] = len(deduped)
            rec["_dup_count"] = 1
            deduped.append(rec)

    # ── Крок 3: будуємо фінальні записи з metadata ───────────────────────────
    final: list[dict] = []
    for rec in deduped:
        meta = build_metadata(rec, rec["en"], rec["uk_human"])
        meta["duplicate_count"] = rec["_dup_count"]

        final.append({
            "id":       rec["id"],
            "version":  rec["version"],
            "en":       rec["en"],
            "uk_human": rec["uk_human"],
            "metadata": meta,
        })

    save_jsonl(final, out_path)
    return final, total_in, empty_count, dup_removed


if __name__ == "__main__":
    import random
    random.seed(42)

    records, total_in, empty_count, dup_removed = run(
        INTERMEDIATE / "classified.jsonl",
        INTERMEDIATE / "filtered.jsonl",
    )

    total_out = len(records)

    # ── Зведення ─────────────────────────────────────────────────────────────
    print(f"\n=== FILTER SUMMARY ===")
    print(f"Записів на вході:          {total_in:>8,}")
    print(f"Видалено (порожні):        {empty_count:>8,}")
    print(f"Видалено (дублікати):      {dup_removed:>8,}")
    print(f"Записів на виході:         {total_out:>8,}")

    # tag_asymmetry
    asym_true  = sum(1 for r in records if r["metadata"]["tag_asymmetry"])
    asym_false = total_out - asym_true
    print(f"\n=== TAG ASYMMETRY ===")
    print(f"tag_asymmetry=true:   {asym_true:>7,}  ({asym_true/total_out*100:.1f}%)")
    print(f"tag_asymmetry=false:  {asym_false:>7,}  ({asym_false/total_out*100:.1f}%)")

    # по класах
    asym_by_class: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in records:
        cls = r["metadata"]["type"]
        asym_by_class[cls][1] += 1
        if r["metadata"]["tag_asymmetry"]:
            asym_by_class[cls][0] += 1
    print("\nПо класах (asym / всього):")
    for cls, (a, t) in sorted(asym_by_class.items(), key=lambda x: -x[1][1]):
        print(f"  {cls:<25} {a:>5,} / {t:>7,}  ({a/t*100:.1f}%)")

    # length_class
    lc_counts: Counter = Counter(r["metadata"]["length_class"] for r in records)
    print(f"\n=== LENGTH CLASS ===")
    for lc in ("short", "medium", "long", "extreme"):
        cnt = lc_counts.get(lc, 0)
        print(f"  {lc:<10} {cnt:>7,}  ({cnt/total_out*100:.1f}%)")

    # 5 повних прикладів
    print(f"\n=== 5 ПРИКЛАДІВ (filtered.jsonl) ===\n")
    for r in random.sample(records, 5):
        print(json.dumps(r, ensure_ascii=False, indent=2))
        print()
