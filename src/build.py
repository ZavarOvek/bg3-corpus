"""
build.py — збірка фінального corpus.jsonl.

Логіка:
  1. Читає filtered.jsonl (186 311 пар) — основа корпусу
  2. Читає gemini_results.jsonl (4 992 записи вибірки)
  3. Для кожного запису filtered:
     - якщо id є у gemini_results і uk_gemini != null:
         uk_gemini = переклад, metadata.in_sample = True
     - якщо id є у gemini_results але uk_gemini = null (FAIL):
         uk_gemini = null, metadata.in_sample = True
     - якщо id НЕ у gemini_results:
         uk_gemini = null, metadata.in_sample = False

Вихід: data/corpus.jsonl
Схема рядка:
  {id, version, en, uk_human, uk_gemini, metadata}
  metadata додає поля: in_sample (bool)
"""

import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

INTERMEDIATE  = Path("data/intermediate")
FILTERED_PATH = INTERMEDIATE / "filtered.jsonl"
GEMINI_PATH   = INTERMEDIATE / "gemini_results.jsonl"
CORPUS_PATH   = Path("data/corpus.jsonl")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def load_gemini_index(path: Path) -> dict[str, str | None]:
    """Повертає {id: uk_gemini} для всіх записів gemini_results."""
    index = {}
    for l in path.open("r", encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        obj = json.loads(l)
        index[obj["id"]] = obj.get("uk_gemini")
    return index


def run(
    filtered_path: Path = FILTERED_PATH,
    gemini_path:   Path = GEMINI_PATH,
    corpus_path:   Path = CORPUS_PATH,
) -> None:
    logger.info("Читаємо %s", filtered_path)
    filtered = load_jsonl(filtered_path)
    logger.info("Читаємо %s", gemini_path)
    gemini_index = load_gemini_index(gemini_path)

    logger.info("Filtered: %d | Gemini index: %d", len(filtered), len(gemini_index))

    corpus_path.parent.mkdir(parents=True, exist_ok=True)

    total        = 0
    with_gemini  = 0
    in_sample    = 0
    not_in_sample = 0

    with corpus_path.open("w", encoding="utf-8") as f:
        for rec in filtered:
            uid = rec["id"]
            meta = dict(rec["metadata"])

            if uid in gemini_index:
                uk_gemini = gemini_index[uid]
                meta["in_sample"] = True
                in_sample += 1
                if uk_gemini is not None:
                    with_gemini += 1
            else:
                uk_gemini = None
                meta["in_sample"] = False
                not_in_sample += 1

            out = {
                "id":        uid,
                "version":   rec["version"],
                "en":        rec["en"],
                "uk_human":  rec["uk_human"],
                "uk_gemini": uk_gemini,
                "metadata":  meta,
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
            total += 1

    logger.info("─" * 50)
    logger.info("CORPUS SUMMARY")
    logger.info("  Всього пар:           %d", total)
    logger.info("  У вибірці (in_sample):%d", in_sample)
    logger.info("    з uk_gemini:        %d  (%.1f%% вибірки)",
                with_gemini, with_gemini / in_sample * 100 if in_sample else 0)
    logger.info("    uk_gemini=null:     %d", in_sample - with_gemini)
    logger.info("  Поза вибіркою:        %d", not_in_sample)
    logger.info("─" * 50)
    logger.info("Збережено → %s", corpus_path)


if __name__ == "__main__":
    run()
