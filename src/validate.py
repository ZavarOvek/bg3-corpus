"""
validate.py — обчислення MT-метрик для корпусу BG3-EN-UK.

Пара: (uk_gemini) vs (uk_human) як reference.

Метрики:
  - BLEU   (sacrebleu, tokenize='13a')
  - METEOR (sacrebleu)
  - TER    (sacrebleu)
  - CHRF   (sacrebleu, word_order=2 = ChrF++)
  - BERTScore (bert-score, model=xlm-roberta-base)

Групування результатів:
  - Aggregate (всі 4 992)
  - По 7 типах тексту
  - tag_asymmetry=true vs false

Перед обчисленням:
  - Стрипуємо HTML-теги (<i>, <b>, <br>, <LSTag...>) з обох сторін
  - Залишаємо плейсхолдери [1],[2] та маркери *...* і ((*...*))
  - Виключаємо uk_human_quality='marker_mismatch' (3 записи)

Виходи:
  data/validation_results.md
  data/validation_raw.jsonl
"""

import json
import logging
import re
from collections import defaultdict
from pathlib import Path

import sacrebleu
from bert_score import score as bert_score_fn
from nltk.translate.meteor_score import meteor_score as nltk_meteor
from nltk.tokenize import word_tokenize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

CORPUS_PATH  = Path("data/corpus.jsonl")
RESULTS_MD   = Path("data/validation_results.md")
RESULTS_JSONL = Path("data/validation_raw.jsonl")

# Модель для BERTScore — багатомовна, підтримує українську
BERT_MODEL = "xlm-roberta-base"

# Regex для стрипу HTML-тегів
TAG_RE = re.compile(r"<[^>]+>", re.IGNORECASE)


def strip_tags(text: str) -> str:
    """Видаляє HTML-теги, зберігає плейсхолдери [N] і маркери."""
    return TAG_RE.sub("", text).strip()


def compute_sacrebleu_metrics(hyps: list[str], refs: list[str]) -> dict:
    """BLEU, METEOR, TER, CHRF++ для списку гіпотез і референсів."""
    bleu = sacrebleu.corpus_bleu(hyps, [refs], tokenize="13a")
    ter  = sacrebleu.corpus_ter(hyps, [refs])
    chrf = sacrebleu.corpus_chrf(hyps, [refs], word_order=2)

    # METEOR через NLTK (sacrebleu 2.x не має corpus_meteor)
    meteor_scores = []
    for h, r in zip(hyps, refs):
        h_tok = word_tokenize(h.lower()) if h.strip() else [""]
        r_tok = word_tokenize(r.lower()) if r.strip() else [""]
        meteor_scores.append(nltk_meteor([r_tok], h_tok))
    meteor_avg = sum(meteor_scores) / len(meteor_scores) if meteor_scores else 0.0

    return {
        "BLEU":   round(bleu.score, 2),
        "METEOR": round(meteor_avg * 100, 2),
        "TER":    round(ter.score, 2),
        "CHRF":   round(chrf.score, 2),
        "n":      len(hyps),
    }


def compute_bertscore(hyps: list[str], refs: list[str], model: str) -> dict:
    """BERTScore P/R/F1."""
    logger.info("  BERTScore: обчислення для %d пар (модель: %s)...", len(hyps), model)
    P, R, F1 = bert_score_fn(
        hyps, refs,
        model_type=model,
        lang="uk",
        verbose=False,
        device=None,
    )
    return {
        "BERTScore_P":  round(P.mean().item() * 100, 2),
        "BERTScore_R":  round(R.mean().item() * 100, 2),
        "BERTScore_F1": round(F1.mean().item() * 100, 2),
    }


def run(
    corpus_path:   Path = CORPUS_PATH,
    results_md:    Path = RESULTS_MD,
    results_jsonl: Path = RESULTS_JSONL,
) -> None:
    # ── Завантаження і фільтрація ─────────────────────────────────────────────
    logger.info("Читаємо %s", corpus_path)
    all_records = []
    with corpus_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                all_records.append(json.loads(line))

    # Тільки вибірка з перекладом
    sample = [
        r for r in all_records
        if r["metadata"].get("in_sample")
        and r.get("uk_gemini") is not None
    ]

    # Виключаємо marker_mismatch
    excluded = [r for r in sample if r["metadata"].get("uk_human_quality") == "marker_mismatch"]
    sample   = [r for r in sample if r["metadata"].get("uk_human_quality") != "marker_mismatch"]

    logger.info("Вибірка: %d записів | Виключено (marker_mismatch): %d",
                len(sample), len(excluded))

    # ── Стрип тегів ───────────────────────────────────────────────────────────
    for r in sample:
        r["_hyp"] = strip_tags(r["uk_gemini"])
        r["_ref"] = strip_tags(r["uk_human"])

    hyps_all = [r["_hyp"] for r in sample]
    refs_all = [r["_ref"] for r in sample]

    # ── Групи ─────────────────────────────────────────────────────────────────
    groups: dict[str, list[dict]] = {"__all__": sample}

    # По типах
    by_type: dict[str, list[dict]] = defaultdict(list)
    for r in sample:
        by_type[r["metadata"]["type"]].append(r)
    groups.update(by_type)

    # tag_asymmetry
    groups["tag_asymmetry=true"]  = [r for r in sample if r["metadata"].get("tag_asymmetry")]
    groups["tag_asymmetry=false"] = [r for r in sample if not r["metadata"].get("tag_asymmetry")]

    # ── BERTScore для всіх одразу ─────────────────────────────────────────────
    logger.info("BERTScore: завантаження моделі %s...", BERT_MODEL)
    P_all, R_all, F1_all = bert_score_fn(
        hyps_all, refs_all,
        model_type=BERT_MODEL,
        lang="uk",
        verbose=False,
        device=None,
    )
    # Зберігаємо per-record BERTScore
    for i, r in enumerate(sample):
        r["_bs_p"]  = P_all[i].item()
        r["_bs_r"]  = R_all[i].item()
        r["_bs_f1"] = F1_all[i].item()

    # ── Обчислення по групах ──────────────────────────────────────────────────
    results: dict[str, dict] = {}
    type_order = ["__all__", "dialogue", "ui_short", "narrative",
                  "mechanic_description", "book_or_document", "telepathic",
                  "ui_keybind", "tag_asymmetry=true", "tag_asymmetry=false"]

    for group_name in type_order:
        recs = groups.get(group_name, [])
        if not recs:
            continue
        logger.info("Метрики для: %s (n=%d)", group_name, len(recs))
        hyps = [r["_hyp"] for r in recs]
        refs = [r["_ref"] for r in recs]

        sb = compute_sacrebleu_metrics(hyps, refs)

        # BERTScore — з вже обчислених per-record
        bs_f1 = round(sum(r["_bs_f1"] for r in recs) / len(recs) * 100, 2)
        bs_p  = round(sum(r["_bs_p"]  for r in recs) / len(recs) * 100, 2)
        bs_r  = round(sum(r["_bs_r"]  for r in recs) / len(recs) * 100, 2)

        results[group_name] = {
            **sb,
            "BERTScore_P":  bs_p,
            "BERTScore_R":  bs_r,
            "BERTScore_F1": bs_f1,
        }

    # ── Збереження validation_raw.jsonl ───────────────────────────────────────
    results_jsonl.parent.mkdir(parents=True, exist_ok=True)
    with results_jsonl.open("w", encoding="utf-8") as f:
        for r in sample:
            out = {
                "id":          r["id"],
                "type":        r["metadata"]["type"],
                "length_class": r["metadata"]["length_class"],
                "tag_asymmetry": r["metadata"].get("tag_asymmetry"),
                "en":          r["en"],
                "uk_human":    r["uk_human"],
                "uk_gemini":   r["uk_gemini"],
                "hyp_clean":   r["_hyp"],
                "ref_clean":   r["_ref"],
                "bertscore_f1": round(r["_bs_f1"] * 100, 2),
            }
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    logger.info("Збережено: %s", results_jsonl)

    # ── Markdown-звіт ─────────────────────────────────────────────────────────
    lines = []
    a = lines.append

    a("# Результати валідації: Gemini vs Human Translation")
    a("")
    a("**Корпус:** BG3-EN-UK | **Пара:** `uk_gemini` (гіпотеза) vs `uk_human` (референс)")
    a("")
    a("**Методологія:**")
    a("- Теги `<i>`, `<b>`, `<br>`, `<LSTag...>` стрипуються перед обчисленням")
    a("- Плейсхолдери `[1]`, `[2]`, маркери `*...*` та `((*...*))` зберігаються")
    a(f"- Виключено {len(excluded)} записи з `uk_human_quality=marker_mismatch`")
    a(f"- BERTScore: модель `{BERT_MODEL}` (багатомовна, підтримує українську)")
    a(f"- **n = {len(sample):,}** пар для обчислення")
    a("")

    # ── Aggregate ──────────────────────────────────────────────────────────────
    a("## 1. Загальні метрики (aggregate)\n")
    ag = results["__all__"]
    a("| Метрика | Значення | Інтерпретація |")
    a("|---------|---------|--------------|")
    a(f"| BLEU | **{ag['BLEU']}** | 0–100, вища = краще |")
    a(f"| METEOR | **{ag['METEOR']}** | 0–100, вища = краще |")
    a(f"| TER | **{ag['TER']}** | 0–∞, нижча = краще |")
    a(f"| ChrF++ | **{ag['CHRF']}** | 0–100, вища = краще |")
    a(f"| BERTScore F1 | **{ag['BERTScore_F1']}** | 0–100, вища = краще |")
    a(f"| BERTScore P | {ag['BERTScore_P']} | |")
    a(f"| BERTScore R | {ag['BERTScore_R']} | |")
    a(f"| n | {ag['n']:,} | |")
    a("")

    # ── По типах ──────────────────────────────────────────────────────────────
    a("## 2. Метрики по типах тексту\n")
    type_names = ["dialogue", "ui_short", "narrative",
                  "mechanic_description", "book_or_document", "telepathic", "ui_keybind"]
    a("| Тип | n | BLEU | METEOR | TER | ChrF++ | BERTScore F1 |")
    a("|-----|---|------|--------|-----|--------|-------------|")
    for t in type_names:
        if t not in results:
            continue
        r = results[t]
        a(f"| `{t}` | {r['n']:,} | {r['BLEU']} | {r['METEOR']} | {r['TER']} | {r['CHRF']} | {r['BERTScore_F1']} |")
    a("")

    # ── Tag asymmetry ──────────────────────────────────────────────────────────
    a("## 3. Метрики: tag_asymmetry\n")
    a("| Група | n | BLEU | METEOR | TER | ChrF++ | BERTScore F1 |")
    a("|-------|---|------|--------|-----|--------|-------------|")
    for g in ["tag_asymmetry=false", "tag_asymmetry=true"]:
        if g not in results:
            continue
        r = results[g]
        a(f"| `{g}` | {r['n']:,} | {r['BLEU']} | {r['METEOR']} | {r['TER']} | {r['CHRF']} | {r['BERTScore_F1']} |")
    a("")

    # ── Нотатки ────────────────────────────────────────────────────────────────
    a("## 4. Нотатки для Розділу 4\n")
    a("### Виключені записи (marker_mismatch)")
    a("")
    if excluded:
        a("| id | EN | причина |")
        a("|----|----|---------|")
        for r in excluded:
            a(f"| `{r['id'][:20]}...` | {r['en'][:60]} | marker_mismatch |")
    a("")
    a("### Обмеження метрик")
    a("")
    a("- **BLEU** чутливий до порядку слів і довжини; при коротких рядках (82.7% корпусу < 100 символів) дає нестабільні результати.")
    a("- **TER** штрафує за перестановки; може бути завищений для вільного перекладу.")
    a("- **BERTScore** краще відображає семантичну схожість, менш чутливий до поверхневих розбіжностей.")
    a("- Офіційний переклад (`uk_human`) є референсом — але він сам може містити помилки або використовувати інший регістр/стиль.")
    a("- Для `ui_keybind` і `telepathic` — малі вибірки (n<100), метрики менш стабільні.")
    a("")

    results_md.parent.mkdir(parents=True, exist_ok=True)
    results_md.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Збережено: %s", results_md)


if __name__ == "__main__":
    run()
