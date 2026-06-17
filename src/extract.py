"""
extract.py — парсинг XML-файлів локалізації BG3.

Витягує (contentuid, version, text) з одного XML-файлу.
Текст зберігається "як є" — з тегами, \n, пробілами.

Вихід: data/intermediate/{en,uk}.jsonl
Формат рядка: {"id": "h...", "version": 1, "text": "..."}
"""

import json
import logging
from pathlib import Path

from lxml import etree

logger = logging.getLogger(__name__)


def parse_loca_xml(xml_path: Path) -> list[dict]:
    """
    Ітеративний парсинг великого XML-файлу локалізації Larian.

    Повертає список {"id": contentuid, "version": int, "text": str}.
    Записи з порожнім текстом включаються (text="").
    """
    records: list[dict] = []
    context = etree.iterparse(xml_path, events=("end",), tag="content")

    for _event, elem in context:
        uid = elem.get("contentuid", "")
        version_raw = elem.get("version", "1")
        text = elem.text or ""

        try:
            version = int(version_raw)
        except ValueError:
            version = 1

        records.append({"id": uid, "version": version, "text": text})
        elem.clear()

    logger.info("Прочитано %d записів з %s", len(records), xml_path.name)
    return records


def save_jsonl(records: list[dict], out_path: Path) -> None:
    """Зберігає записи у JSONL."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    logger.info("Збережено %d записів → %s", len(records), out_path)


def load_jsonl(jsonl_path: Path) -> list[dict]:
    """Завантажує JSONL-файл у список словників."""
    records = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            records.append(json.loads(line))
    return records


if __name__ == "__main__":
    import random

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    BASE = Path(".")
    EN_XML = BASE / "Localization" / "english.loca.xml"
    UK_XML = BASE / "Localization" / "ukrainian.loca.xml"
    INTERMEDIATE = BASE / "data" / "intermediate"

    logger.info("--- EN ---")
    en_records = parse_loca_xml(EN_XML)
    save_jsonl(en_records, INTERMEDIATE / "en.jsonl")

    logger.info("--- UK ---")
    uk_records = parse_loca_xml(UK_XML)
    save_jsonl(uk_records, INTERMEDIATE / "uk.jsonl")

    # 10 випадкових прикладів з EN
    print(f"\n=== EN: {len(en_records):,} записів ===")
    print(f"=== UK: {len(uk_records):,} записів ===\n")
    print("--- 10 випадкових прикладів з EN ---\n")
    sample = random.sample(en_records, min(10, len(en_records)))
    for i, rec in enumerate(sample, 1):
        preview = rec["text"][:200].replace("\n", "\\n")
        print(f"[{i}] id={rec['id']} ver={rec['version']}")
        print(f"     {preview!r}")
        print()
