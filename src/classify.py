"""
classify.py — класифікація записів за metadata.type.

Евристики (за пріоритетом):
  1. telepathic           — EN починається з '((*'
  2. narrative            — EN починається з '*' і закінчується на '*'
  3. ui_keybind           — EN починається з '[IE_', '[GLO_', '[GEN_'
  4. book_or_document     — EN починається з '[', вміст дужок: >=10 симв, є пробіл і мала літера
  5. mechanic_description — EN містить '<LSTag'
  6. ui_short             — довжина < 30 І не закінчується на . ? ! : ) ] "
  7. dialogue             — все інше
  8. other                — fallback (не очікується)

Поле metadata.uk_human_quality:
  'clean'          — без відомих дефектів маркера
  'marker_mismatch' — дефект UK-маркера (з перевірки check_telepathic_uk.py
                      і telepathic_extras)

Читає: data/intermediate/aligned.jsonl
Пише:  data/intermediate/classified.jsonl
"""

import json
import random
import re
from collections import Counter
from pathlib import Path

INTERMEDIATE = Path("data/intermediate")

PUNCT_END_RE  = re.compile(r"[.?!:)\]\"'»…—\-]$")
LSTAG_RE      = re.compile(r"<LSTag", re.IGNORECASE)
KEYBIND_RE    = re.compile(r"^\[(IE_|GLO_|GEN_)")
# Ідентифікатори: чисте число, ALL_CAPS_WITH_UNDERSCORES, або ALLCAPS без пробілів
BRACKET_ID_RE = re.compile(r"^\[(\d+|[A-Z][A-Z0-9 _]*)\]")


def _is_book_bracket(stripped: str) -> bool:
    """
    Перевіряє, чи вміст першої пари дужок є змістовним описом (книга/документ),
    а не технічним ідентифікатором чи числом.

    Правила для вмісту між [ і першим ]:
      - довжина >= 10 символів
      - містить хоча б один пробіл
      - містить хоча б одну малу літеру
      - НЕ є чистим числом
      - НЕ є CAPS_WITH_UNDERSCORES або ALL CAPS без малих
    """
    bracket_end = stripped.find("]")
    if bracket_end < 0:
        return False
    content = stripped[1:bracket_end]

    if len(content) < 10:
        return False
    if " " not in content:
        return False
    if not any(c.islower() for c in content):
        return False
    if content.strip().isdigit():
        return False
    return True

# Відомі дефектні id (з check_telepathic_uk.py + telepathic_extras)
MARKER_MISMATCH_IDS: frozenset[str] = frozenset({
    "hc487b8feg808cg4281gb27eg2854f0f90b33",  # partial_open UK маркер
    "h315e1420g6bf4g4e4cg8381gdcf75545cc38",  # <br> хвіст після *))
    "h93881c0agc132g439fg8979g36c9ba7ef54d",  # <br> хвіст після *))
})


def classify(en: str) -> str:
    """Повертає тип запису за EN-текстом."""
    stripped = en.strip()

    # 1. telepathic
    if stripped.startswith("((*"):
        return "telepathic"

    # 2. narrative: * на початку і в кінці
    if stripped.startswith("*") and stripped.endswith("*") and len(stripped) >= 3:
        return "narrative"

    # 3. ui_keybind: технічні префікси [IE_|GLO_|GEN_]
    if KEYBIND_RE.match(stripped):
        return "ui_keybind"

    # 4. book_or_document: позитивне визначення через _is_book_bracket
    if stripped.startswith("[") and _is_book_bracket(stripped):
        return "book_or_document"

    # 5. mechanic_description: містить <LSTag
    if LSTAG_RE.search(stripped):
        return "mechanic_description"

    # 6. ui_short: коротко і без фінальної пунктуації
    if len(stripped) < 30 and not PUNCT_END_RE.search(stripped):
        return "ui_short"

    # 7. dialogue
    return "dialogue"


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    random.seed(42)

    records = load_jsonl(INTERMEDIATE / "aligned.jsonl")

    classified = []
    for rec in records:
        rec_type = classify(rec["en"])
        uk_quality = "marker_mismatch" if rec["id"] in MARKER_MISMATCH_IDS else "clean"
        classified.append({**rec, "metadata": {"type": rec_type, "uk_human_quality": uk_quality}})

    save_jsonl(classified, INTERMEDIATE / "classified.jsonl")

    # Розподіл
    total = len(classified)
    counts: Counter = Counter(r["metadata"]["type"] for r in classified)

    print(f"\n=== РОЗПОДІЛ КЛАСІВ ({total:,} записів) ===\n")
    for cls, cnt in counts.most_common():
        print(f"  {cls:<25} {cnt:>7,}  ({cnt/total*100:.1f}%)")

    # 5 прикладів кожного класу
    by_class: dict[str, list[dict]] = {}
    for r in classified:
        by_class.setdefault(r["metadata"]["type"], []).append(r)

    order = [c for c, _ in counts.most_common()]
    for cls in order:
        recs = by_class[cls]
        print(f"\n--- {cls} ({len(recs):,}) ---")
        for r in random.sample(recs, min(5, len(recs))):
            print(f"  EN: {r['en'][:120]!r}")
            print(f"  UK: {r['uk_human'][:120]!r}")
            print()
