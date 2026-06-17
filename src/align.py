"""
align.py — вирівнювання EN і UK записів за contentuid.

Читає data/intermediate/en.jsonl і uk.jsonl.
Виходи:
  - data/intermediate/aligned.jsonl  — {id, version, en, uk_human}
  - data/intermediate/en_only.jsonl  — {id, version, text, reason}
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

INTERMEDIATE = Path("data/intermediate")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Збережено %d записів → %s", len(records), path)


def align(en_records: list[dict], uk_records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Вирівнює EN і UK за id (contentuid).

    Returns:
        (aligned, en_only)
        aligned:  [{id, version, en, uk_human}, ...]
        en_only:  [{id, version, text, reason}, ...]
    """
    uk_by_id: dict[str, str] = {r["id"]: r["text"] for r in uk_records}

    aligned: list[dict] = []
    en_only: list[dict] = []

    for rec in en_records:
        uid = rec["id"]
        if uid in uk_by_id:
            aligned.append({
                "id": uid,
                "version": rec["version"],
                "en": rec["text"],
                "uk_human": uk_by_id[uid],
            })
        else:
            en_only.append({
                "id": uid,
                "version": rec["version"],
                "text": rec["text"],
                "reason": "no_uk_translation",
            })

    logger.info(
        "Вирівняно: %d пар | EN-only: %d",
        len(aligned), len(en_only),
    )
    return aligned, en_only


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    en_records = load_jsonl(INTERMEDIATE / "en.jsonl")
    uk_records = load_jsonl(INTERMEDIATE / "uk.jsonl")

    aligned, en_only = align(en_records, uk_records)

    save_jsonl(aligned, INTERMEDIATE / "aligned.jsonl")
    save_jsonl(en_only, INTERMEDIATE / "en_only.jsonl")

    print(f"\n=== РЕЗУЛЬТАТ ===")
    print(f"Вирівняних пар:  {len(aligned):,}")
    print(f"EN-only:         {len(en_only):,}")
    print(f"\n--- 10 прикладів aligned ---\n")
    import random
    for rec in random.sample(aligned, 10):
        print(f"id={rec['id']} ver={rec['version']}")
        print(f"  EN: {rec['en'][:120]!r}")
        print(f"  UK: {rec['uk_human'][:120]!r}")
        print()
