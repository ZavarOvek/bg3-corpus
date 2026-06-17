"""
scout_tags.py — розвідка тегів і структури english.loca.xml.

Інвентаризує:
- Всі унікальні теги в трикутних дужках всередині <content>
- Для кожного: кількість входжень, 3-5 прикладів
- Для тегів з атрибутами — скільки мають непорожні значення
- Частоту записів що починаються/закінчуються на *
- Частоту плейсхолдерів [N]
- Розподіл довжин записів

Результат: data/intermediate/tags_inventory.md
"""

import logging
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

EN_XML = Path("Localization/english.loca.xml")
OUT_MD = Path("data/intermediate/tags_inventory.md")

# Витягує все що схоже на HTML/XML теги
TAG_RE = re.compile(r"<(/?\w[\w:.-]*)([^>]*)>")
# Атрибути тегів
ATTR_RE = re.compile(r'(\w+)=["\']([^"\']*)["\']')
# Плейсхолдери [1], [2], тощо
PLACEHOLDER_RE = re.compile(r"\[(\d+)\]")
# Записи що починаються або закінчуються на *
ITALIC_MARKER_RE = re.compile(r"^\*.*\*$", re.DOTALL)


def parse_all(xml_path: Path) -> list[tuple[str, str]]:
    """
    Швидкий ітеративний парсинг великого XML.
    Повертає [(contentuid, text), ...].
    """
    records = []
    context = etree.iterparse(xml_path, events=("end",), tag="content")
    for _event, elem in context:
        uid = elem.get("contentuid", "")
        text = elem.text or ""
        records.append((uid, text))
        elem.clear()
    logger.info("Прочитано %d записів", len(records))
    return records


def analyse(records: list[tuple[str, str]]) -> dict:
    tag_counts: Counter = Counter()
    tag_examples: defaultdict[str, list[str]] = defaultdict(list)
    tag_attr_counts: defaultdict[str, Counter] = defaultdict(Counter)
    tag_attr_nonempty: defaultdict[str, Counter] = defaultdict(Counter)

    placeholder_count = 0
    italic_marker_count = 0  # записи що починаються і закінчуються на *
    italic_marker_examples: list[str] = []

    lengths: list[int] = []

    for _uid, text in records:
        lengths.append(len(text))

        # Плейсхолдери
        if PLACEHOLDER_RE.search(text):
            placeholder_count += 1

        # *курсив*
        if ITALIC_MARKER_RE.match(text.strip()):
            italic_marker_count += 1
            if len(italic_marker_examples) < 5:
                italic_marker_examples.append(text.strip()[:120])

        # Теги
        for m in TAG_RE.finditer(text):
            tag_name = m.group(1).lstrip("/").lower()
            full_tag = m.group(0)
            tag_counts[tag_name] += 1
            if len(tag_examples[tag_name]) < 5:
                # контекст: 30 символів до і після тегу
                start = max(0, m.start() - 30)
                end = min(len(text), m.end() + 30)
                snippet = text[start:end].replace("\n", "\\n")
                tag_examples[tag_name].append(snippet)

            # Атрибути
            for attr_name, attr_val in ATTR_RE.findall(m.group(2)):
                tag_attr_counts[tag_name][attr_name] += 1
                if attr_val.strip():
                    tag_attr_nonempty[tag_name][attr_name] += 1

    return {
        "total": len(records),
        "tag_counts": tag_counts,
        "tag_examples": tag_examples,
        "tag_attr_counts": tag_attr_counts,
        "tag_attr_nonempty": tag_attr_nonempty,
        "placeholder_count": placeholder_count,
        "italic_marker_count": italic_marker_count,
        "italic_marker_examples": italic_marker_examples,
        "lengths": lengths,
    }


def length_stats(lengths: list[int]) -> dict:
    lengths_sorted = sorted(lengths)
    n = len(lengths_sorted)
    return {
        "min": lengths_sorted[0],
        "p5": lengths_sorted[int(n * 0.05)],
        "median": statistics.median(lengths_sorted),
        "mean": round(statistics.mean(lengths_sorted), 1),
        "p95": lengths_sorted[int(n * 0.95)],
        "p99": lengths_sorted[int(n * 0.99)],
        "max": lengths_sorted[-1],
    }


def write_report(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ls = length_stats(data["lengths"])
    total = data["total"]

    lines = []
    a = lines.append

    a("# Tags Inventory — english.loca.xml\n")
    a(f"**Всього записів:** {total:,}\n")

    a("## Розподіл довжин (символів)\n")
    a(f"| Метрика | Значення |")
    a(f"|---------|----------|")
    a(f"| min     | {ls['min']} |")
    a(f"| p5      | {ls['p5']} |")
    a(f"| median  | {ls['median']} |")
    a(f"| mean    | {ls['mean']} |")
    a(f"| p95     | {ls['p95']} |")
    a(f"| p99     | {ls['p99']} |")
    a(f"| max     | {ls['max']} |")
    a("")

    a("## Спеціальні маркери\n")
    a(f"- Записи з плейсхолдерами `[N]`: **{data['placeholder_count']:,}** ({data['placeholder_count']/total*100:.1f}%)")
    a(f"- Записи у `*зірочках*` (наративний монолог): **{data['italic_marker_count']:,}** ({data['italic_marker_count']/total*100:.1f}%)")
    a("")

    if data["italic_marker_examples"]:
        a("### Приклади `*зірочок*`\n")
        for ex in data["italic_marker_examples"]:
            a(f"```\n{ex}\n```")
        a("")

    a("## Унікальні теги (за частотою)\n")
    a(f"| Тег | Входжень | % записів |")
    a(f"|-----|----------|-----------|")
    for tag, count in data["tag_counts"].most_common():
        a(f"| `<{tag}>` | {count:,} | {count/total*100:.2f}% |")
    a("")

    a("## Деталі по тегах\n")
    for tag, count in data["tag_counts"].most_common():
        a(f"### `<{tag}>` — {count:,} входжень\n")

        attrs = data["tag_attr_counts"].get(tag, {})
        if attrs:
            a("**Атрибути:**\n")
            a("| Атрибут | Всього | Непорожніх |")
            a("|---------|--------|------------|")
            for attr, acnt in attrs.most_common():
                nonempty = data["tag_attr_nonempty"].get(tag, {}).get(attr, 0)
                a(f"| `{attr}` | {acnt:,} | {nonempty:,} |")
            a("")

        examples = data["tag_examples"].get(tag, [])
        if examples:
            a("**Приклади контексту:**\n")
            for ex in examples:
                a(f"```\n...{ex}...\n```")
        a("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Звіт збережено: %s", out_path)


if __name__ == "__main__":
    logger.info("Читаємо %s", EN_XML)
    records = parse_all(EN_XML)
    logger.info("Аналізуємо...")
    data = analyse(records)
    write_report(data, OUT_MD)

    # Короткий summary у stdout
    ls = length_stats(data["lengths"])
    print(f"\n=== SUMMARY ===")
    print(f"Записів: {data['total']:,}")
    print(f"Довжини: min={ls['min']} | median={ls['median']} | p95={ls['p95']} | max={ls['max']}")
    print(f"Плейсхолдери [N]: {data['placeholder_count']:,} ({data['placeholder_count']/data['total']*100:.1f}%)")
    print(f"*Зірочки*: {data['italic_marker_count']:,} ({data['italic_marker_count']/data['total']*100:.1f}%)")
    print(f"\nТеги:")
    for tag, count in data["tag_counts"].most_common():
        print(f"  <{tag}>: {count:,}")
