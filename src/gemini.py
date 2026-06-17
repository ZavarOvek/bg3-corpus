"""
gemini.py — генерація синтетичних перекладів через Google Gemini API.

Модель:  gemini-3.1-flash-lite
SDK:     google-genai (новий, google.generativeai deprecated з 2026)
Вхід:    data/intermediate/sample.jsonl
Вихід:   data/intermediate/gemini_results.jsonl

Поведінка:
  - Один запит = один запис (без батчингу)
  - Інкрементальне збереження після кожного запиту
  - Resume: пропускає id, що вже є у gemini_results.jsonl
  - 429 / 5xx → exponential backoff (tenacity): 1s → 2s → 4s → 8s → 16s → 32s
  - 400 / 403 → зупинка з ясним логом, без повторів
  - Ключ API тільки з .env → RuntimeError якщо відсутній

НЕ ЗАПУСКАТИ без явного підтвердження промпта.
Перший тест: python src/gemini.py --limit 10
"""

import json
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Явний шлях до .env — працює незалежно від cwd при імпорті модуля
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(_ENV_PATH)

logger = logging.getLogger(__name__)

INTERMEDIATE = Path("data/intermediate")
PROMPTS_DIR  = Path("prompts")

SAMPLE_PATH  = INTERMEDIATE / "sample.jsonl"
RESULTS_PATH = INTERMEDIATE / "gemini_results.jsonl"
PROMPT_PATH  = PROMPTS_DIR  / "gemini_v1.txt"

# ── Параметри моделі ──────────────────────────────────────────────────────────

MODEL_NAME        = "gemini-3.1-flash-lite"
TEMPERATURE       = 0.2
TOP_P             = 0.9
TOP_K             = 40
MAX_OUTPUT_TOKENS = 2048

# Безкоштовний tier: 15 RPM → 4.5с між запитами з запасом
SLEEP_BETWEEN = 4.5


# ── Класи помилок для диференційованого retry ─────────────────────────────────

class RetryableError(Exception):
    """429 rate limit або 5xx сервера — повторюємо з backoff."""

class FatalError(Exception):
    """400 / 403 — зупиняємось, не повторюємо."""


def _classify_api_error(exc: Exception) -> Exception:
    """Перетворює виняток Google API у RetryableError або FatalError."""
    msg = str(exc).lower()
    if "429" in msg or "resource_exhausted" in msg or "quota" in msg:
        return RetryableError(str(exc))
    if "500" in msg or "503" in msg or "unavailable" in msg or "internal" in msg:
        return RetryableError(str(exc))
    if "400" in msg or "403" in msg or "invalid" in msg or "permission" in msg:
        return FatalError(str(exc))
    return RetryableError(str(exc))


# ── Промпт ────────────────────────────────────────────────────────────────────

def load_prompt_template(path: Path = PROMPT_PATH) -> str:
    return path.read_text(encoding="utf-8")


def build_user_message(template: str, en_text: str, rec_type: str) -> str:
    """Підставляє {type} і {en_text} у шаблон промпта."""
    return template.replace("{type}", rec_type).replace("{en_text}", en_text)


# ── Ініціалізація клієнта ─────────────────────────────────────────────────────

def init_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY не знайдено. Створіть файл .env з рядком:\n"
            "GEMINI_API_KEY=your_key_here"
        )
    logger.info("GEMINI_API_KEY знайдено (довжина=%d символів)", len(api_key))
    return genai.Client(api_key=api_key)


# ── Один запит з диференційованим retry ──────────────────────────────────────

@retry(
    retry=retry_if_exception_type(RetryableError),
    wait=wait_exponential(multiplier=1, min=1, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def _call_api(client: genai.Client, user_message: str) -> str:
    """
    Надсилає один запит до Gemini. Повертає текст відповіді.
    RetryableError → tenacity повторює (backoff 1→2→4→8→16→32с).
    FatalError     → піднімається одразу, без повторів.
    """
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                top_p=TOP_P,
                top_k=TOP_K,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        return response.text.strip()
    except FatalError:
        raise
    except Exception as exc:
        classified = _classify_api_error(exc)
        raise classified from exc


def translate_one(
    client: genai.Client,
    template: str,
    rec: dict,
) -> str | None:
    """
    Перекладає один запис. Повертає рядок або None при провалі.
    Помилки логуються БЕЗ значення API ключа.
    """
    rec_type     = rec["metadata"]["type"]
    user_message = build_user_message(template, rec["en"], rec_type)
    try:
        return _call_api(client, user_message)
    except FatalError as exc:
        logger.error("FATAL (зупинка) id=%s: %s", rec["id"], exc)
        return None
    except RetryableError as exc:
        logger.error("FAIL після 6 спроб id=%s: %s", rec["id"], exc)
        return None
    except Exception as exc:
        logger.error("Невідома помилка id=%s: %s", rec["id"], exc)
        return None


# ── Resume ────────────────────────────────────────────────────────────────────

def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_done_ids(results_path: Path) -> set[str]:
    """
    Повертає id записів що вже мають uk_gemini != null.
    Побічний ефект: якщо у файлі є рядки з uk_gemini=null (FAIL з минулого
    запуску), вони видаляються — файл перезаписується тільки з OK рядками.
    Це гарантує чистий resume без дублікатів id.
    """
    if not results_path.exists():
        return set()
    ok_lines: list[str] = []
    done: set[str] = set()
    null_count = 0
    with results_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("uk_gemini") is not None:
                done.add(obj["id"])
                ok_lines.append(line)
            else:
                null_count += 1
    if null_count:
        logger.warning("Resume: видаляємо %d FAIL-рядків (uk_gemini=null) з файлу", null_count)
        results_path.write_text("\n".join(ok_lines) + "\n", encoding="utf-8")
    logger.info("Resume: %d вже перекладених записів", len(done))
    return done


# ── Основний цикл ─────────────────────────────────────────────────────────────

def run(
    sample_path: Path = SAMPLE_PATH,
    results_path: Path = RESULTS_PATH,
    limit: int | None = None,
) -> None:
    """
    Перекладає записи з sample_path, пише у results_path інкрементально.

    Args:
        sample_path:  вхідний JSONL
        results_path: вихідний JSONL (append при resume)
        limit:        зупинитись після N нових перекладів (тест: 10 / 100 / 1000)
    """
    records  = load_jsonl(sample_path)
    done_ids = load_done_ids(results_path)

    pending = [r for r in records if r["id"] not in done_ids]
    if limit:
        pending = pending[:limit]

    logger.info(
        "Вибірка: %d | вже готово: %d | до перекладу: %d",
        len(records), len(done_ids), len(pending),
    )
    if not pending:
        logger.info("Нічого робити — всі записи вже перекладено.")
        return

    client   = init_client()
    template = load_prompt_template()

    results_path.parent.mkdir(parents=True, exist_ok=True)

    ok_count   = 0
    fail_count = 0

    with results_path.open("a", encoding="utf-8") as f:
        for i, rec in enumerate(pending, 1):
            translation = translate_one(client, template, rec)

            result = {
                "id":        rec["id"],
                "en":        rec["en"],
                "uk_human":  rec["uk_human"],
                "uk_gemini": translation,
                "metadata":  rec["metadata"],
            }
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()

            if translation:
                ok_count += 1
                logger.info("[%d/%d] OK   id=%s", i, len(pending), rec["id"])
            else:
                fail_count += 1
                logger.warning("[%d/%d] FAIL id=%s", i, len(pending), rec["id"])

            if i < len(pending):
                time.sleep(SLEEP_BETWEEN)

    logger.info(
        "Завершено. OK: %d | FAIL: %d | Файл: %s",
        ok_count, fail_count, results_path,
    )


# ── Точка входу ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    _LOG_DIR = Path("logs")
    _LOG_DIR.mkdir(exist_ok=True)
    _log_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    _console = logging.StreamHandler()
    _console.setFormatter(_log_fmt)

    _file_h = logging.FileHandler(_LOG_DIR / "gemini_run.log", encoding="utf-8")
    _file_h.setFormatter(_log_fmt)

    logging.basicConfig(level=logging.INFO, handlers=[_console, _file_h])

    parser = argparse.ArgumentParser(description="Gemini переклад BG3 корпусу")
    parser.add_argument("--limit",  type=int,  default=None,
                        help="Перекласти тільки N записів (тест: 10 / 100 / 1000)")
    parser.add_argument("--sample", type=Path, default=SAMPLE_PATH)
    parser.add_argument("--out",    type=Path, default=RESULTS_PATH)
    args = parser.parse_args()

    run(sample_path=args.sample, results_path=args.out, limit=args.limit)
