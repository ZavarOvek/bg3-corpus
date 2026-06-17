# TECHNICAL.md — Технічна документація пайплайну BG3-EN-UK

> Документ призначений для додатків дипломної роботи «Створення паралельного корпусу для машинного перекладу на основі текстів відеоігор» (КНУ ім. Тараса Шевченка, 2026).
> Описує всі 9 модулів пайплайну, формати даних, послідовність запуску та технічні рішення.

---

## 1. Структура проєкту

```
bg3-corpus/
├── Localization/                    # Вхідні XML (не публікуються)
│   ├── english.loca.xml             # ~150 MB, 232 876 рядків
│   └── ukrainian.loca.xml           # ~140 MB, 218 232 рядків
│
├── src/                             # Модулі пайплайну
│   ├── scout_tags.py                # 0. Розвідка структури XML
│   ├── extract.py                   # 1. XML → JSONL
│   ├── align.py                     # 2. Вирівнювання EN-UK
│   ├── classify.py                  # 3. Класифікація 7 типів
│   ├── filter.py                    # 4. Дедуплікація і metadata
│   ├── gemini.py                    # 5. Переклад через Gemini API
│   ├── build.py                     # 6. Збірка corpus.jsonl
│   ├── stats.py                     # 7. Описова статистика
│   └── validate.py                  # 8. MT-метрики
│
├── prompts/
│   └── gemini_v1.txt                # Фінальний промпт (v3)
│
├── data/
│   ├── corpus.jsonl                 # Фінальний корпус (186 311 пар)
│   ├── stats.md                     # Описова статистика
│   ├── validation_results.md        # MT-метрики
│   ├── validation_raw.jsonl         # Per-record BERTScore
│   └── intermediate/                # Проміжні файли
│       ├── en.jsonl                 # 232 876 EN-записів
│       ├── uk.jsonl                 # 218 232 UK-записів
│       ├── en_only.jsonl            # 14 644 EN без перекладу
│       ├── aligned.jsonl            # 218 232 EN-UK пар
│       ├── classified.jsonl         # 218 232 з metadata.type
│       ├── filtered.jsonl           # 186 311 після filter
│       ├── sample.jsonl             # 4 992 для Gemini
│       ├── gemini_results.jsonl     # 4 992 перекладів
│       └── tags_inventory.md        # Звіт scout_tags
│
├── logs/
│   └── gemini_run.log               # Журнал Gemini-сесій
│
├── .env                             # GEMINI_API_KEY (не публікується)
├── pyproject.toml
├── requirements.txt
├── TECHNICAL.md                     # Цей файл
└── README.md
```

---

## 2. Послідовність запуску

Повний цикл від вихідних XML до фінальних метрик:

```bash
# Передумова: Python 3.11+, залежності встановлено
pip install -r requirements.txt
python -m nltk.downloader punkt wordnet

# 0. (Одноразово) Розвідка структури даних
python src/scout_tags.py
# → data/intermediate/tags_inventory.md

# 1. XML → JSONL
python src/extract.py
# → data/intermediate/en.jsonl   (232 876 записів)
# → data/intermediate/uk.jsonl   (218 232 записів)

# 2. Вирівнювання
python src/align.py
# → data/intermediate/aligned.jsonl  (218 232 пар)
# → data/intermediate/en_only.jsonl  (14 644 EN-only)

# 3. Класифікація
python src/classify.py
# → data/intermediate/classified.jsonl

# 4. Фільтрація
python src/filter.py
# → data/intermediate/filtered.jsonl (186 311 пар)

# 5. Gemini-переклад (повторювати щодня до завершення вибірки)
python src/gemini.py              # повний прогін (resume автоматичний)
python src/gemini.py --limit 10   # тест: тільки 10 записів
# → data/intermediate/gemini_results.jsonl (4 992 записів)

# 6. Збірка фінального корпусу
python src/build.py
# → data/corpus.jsonl (186 311 пар)

# 7. Статистика
python src/stats.py
# → data/stats.md

# 8. Валідація
python src/validate.py
# → data/validation_results.md
# → data/validation_raw.jsonl
```

---

## 3. Формати проміжних файлів

### 3.1 en.jsonl / uk.jsonl (після extract.py)

Один запис на рядок:
```json
{
  "id": "h000006d4gcefbg4092gbb39gfeb27a3bb0a7",
  "version": 1,
  "text": "Dust. On.<i> </i>My. <i>Tongue!</i>"
}
```

| Поле | Тип | Опис |
|------|-----|------|
| `id` | string | `contentuid` з Larian XML — унікальний хеш рядка |
| `version` | int | Версія локалізації (зазвичай 1) |
| `text` | string | Текст as-is, з тегами і пробілами |

---

### 3.2 aligned.jsonl (після align.py)

```json
{
  "id": "h000006d4gcefbg4092gbb39gfeb27a3bb0a7",
  "version": 1,
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!"
}
```

---

### 3.3 classified.jsonl (після classify.py)

Додає поле `metadata` з `type` і `uk_human_quality`:
```json
{
  "id": "h000006d4g...",
  "version": 1,
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!",
  "metadata": {
    "type": "dialogue",
    "uk_human_quality": "clean"
  }
}
```

---

### 3.4 filtered.jsonl (після filter.py)

Повна схема з усіма metadata-прапорами:
```json
{
  "id": "h000006d4g...",
  "version": 1,
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!",
  "metadata": {
    "type": "dialogue",
    "length_class": "short",
    "char_count_en": 37,
    "char_count_uk": 22,
    "has_lstag": false,
    "has_italic": true,
    "has_bold": false,
    "has_br": false,
    "has_placeholder": false,
    "tag_asymmetry": true,
    "tag_asymmetry_details": {"i": [3, 1]},
    "uk_human_quality": "clean",
    "duplicate_count": 1
  }
}
```

---

### 3.5 gemini_results.jsonl (після gemini.py)

```json
{
  "id": "h000006d4g...",
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!",
  "uk_gemini": "Пил. На. <i>Моєму.</i> <i>Язиці!</i>",
  "metadata": {
    "type": "dialogue",
    "length_class": "short",
    ...
  }
}
```

При FAIL (після 6 спроб): `"uk_gemini": null`.

---

### 3.6 corpus.jsonl (після build.py)

Фінальна схема — розширює filtered.jsonl полями `uk_gemini` і `in_sample`:
```json
{
  "id": "h000006d4g...",
  "version": 1,
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!",
  "uk_gemini": "Пил. На. <i>Моєму.</i> <i>Язиці!</i>",
  "metadata": {
    "type": "dialogue",
    "length_class": "short",
    "char_count_en": 37,
    "char_count_uk": 22,
    "has_lstag": false,
    "has_italic": true,
    "has_bold": false,
    "has_br": false,
    "has_placeholder": false,
    "tag_asymmetry": true,
    "tag_asymmetry_details": {"i": [3, 1]},
    "uk_human_quality": "clean",
    "duplicate_count": 1,
    "in_sample": true
  }
}
```

Для записів поза вибіркою: `"uk_gemini": null, "in_sample": false`.

---

### 3.7 validation_raw.jsonl (після validate.py)

Per-record результати з BERTScore F1:
```json
{
  "id": "h000006d4g...",
  "type": "dialogue",
  "length_class": "short",
  "tag_asymmetry": true,
  "en": "Dust. On.<i> </i>My. <i>Tongue!</i>",
  "uk_human": "<i>Повний рот</i>... піску!",
  "uk_gemini": "Пил. На. <i>Моєму.</i> <i>Язиці!</i>",
  "hyp_clean": "Пил. На. Моєму. Язиці!",
  "ref_clean": "Повний рот... піску!",
  "bertscore_f1": 83.77
}
```

---

## 4. Опис модулів

---

### 4.0 scout_tags.py

**Призначення:** Одноразова розвідка структури XML-файлу перед побудовою пайплайну. Інвентаризує всі теги всередині `<content>`, підраховує входження, збирає атрибути і приклади контексту. Запускається один раз на початку проєкту.

**Вхідні файли:**
- `Localization/english.loca.xml` (~150 MB)

**Вихідні файли:**
- `data/intermediate/tags_inventory.md` — Markdown-звіт з повним переліком тегів

**Ключові функції:**

```python
parse_all(xml_path: Path) -> list[tuple[str, str]]
```
Ітеративний парсинг великого XML через `lxml.etree.iterparse`. Повертає список `(contentuid, text)`. Кожен елемент одразу звільняється (`elem.clear()`) для контролю пам'яті.

```python
analyse(records: list[tuple[str, str]]) -> dict
```
Збирає статистику: `Counter` тегів, приклади контексту (±30 символів), підрахунок атрибутів і значень, кількість плейсхолдерів `[N]`, кількість записів у `*зірочках*`.

```python
length_stats(lengths: list[int]) -> dict
```
Обчислює min, p5, median, mean, p95, p99, max довжин записів.

```python
write_report(data: dict, out_path: Path) -> None
```
Формує Markdown-звіт з таблицями: розподіл довжин, теги за частотою, деталі атрибутів, приклади.

**Залежності:** `lxml`, `re`, `statistics`, `collections`

**Особливості реалізації:**
- `etree.iterparse` з тегом `"content"` — парсить лише цільові елементи без завантаження всього DOM (~150 MB XML) у пам'ять
- `elem.clear()` після кожного елемента — стандартний прийом для ітеративного парсингу lxml

**Час виконання:** ~25–40 секунд на `english.loca.xml` (~150 MB)

---

### 4.1 extract.py

**Призначення:** Парсинг XML-файлів локалізації Larian і збереження у JSONL. Текст зберігається «як є» — з HTML-подібними тегами, переносами рядків і пробілами, щоб не втратити семантично значущу розмітку.

**Вхідні файли:**
- `Localization/english.loca.xml`
- `Localization/ukrainian.loca.xml`

**Вихідні файли:**
- `data/intermediate/en.jsonl` (232 876 записів)
- `data/intermediate/uk.jsonl` (218 232 записів)

**Ключові функції:**

```python
parse_loca_xml(xml_path: Path) -> list[dict]
```
Ітеративний парсинг через `etree.iterparse(events=("end",), tag="content")`. Для кожного елемента `<content>` витягує атрибути `contentuid` і `version`, а також `elem.text`. Порожні тексти зберігаються (`text=""`). Повертає `[{"id": str, "version": int, "text": str}]`.

```python
save_jsonl(records: list[dict], out_path: Path) -> None
```
Зберігає список словників у JSONL (UTF-8, `ensure_ascii=False`).

```python
load_jsonl(jsonl_path: Path) -> list[dict]
```
Завантажує JSONL-файл у список словників.

**Залежності:** `lxml`, `json`, `pathlib`

**Особливості реалізації:**
- Формат Larian `.loca.xml`: кожен рядок тексту є елементом `<content contentuid="h..." version="N">текст</content>` у загальній обгортці `<contentList>`
- `elem.clear()` після обробки — обов'язково для великих XML, інакше пам'ять зростає лінійно
- `version` конвертується в `int` з fallback до 1 при `ValueError`
- Теги `<i>`, `<b>`, `<br>`, `<LSTag Tooltip="...">` всередині тексту зберігаються — вони є частиною локалізації гри, несуть семантику (курсив = внутрішній голос персонажа, `LSTag` = інтерактивна підказка в UI)

**Час виконання:** ~30–50 секунд на файл (~150 MB XML)

---

### 4.2 align.py

**Призначення:** Вирівнювання англійських і українських записів у EN-UK пари за `contentuid`. EN-записи без відповідного UK-запису зберігаються окремо для аналізу покриття.

**Вхідні файли:**
- `data/intermediate/en.jsonl`
- `data/intermediate/uk.jsonl`

**Вихідні файли:**
- `data/intermediate/aligned.jsonl` (218 232 пар `{id, version, en, uk_human}`)
- `data/intermediate/en_only.jsonl` (14 644 записів `{id, version, text, reason}`)

**Ключові функції:**

```python
align(en_records: list[dict], uk_records: list[dict]) -> tuple[list[dict], list[dict]]
```
Будує `dict[id → uk_text]` з UK-записів, потім ітерує по EN-записах. EN-записи з відповідним UK → у `aligned`, без → у `en_only` з `reason="no_uk_translation"`. Повертає `(aligned, en_only)`.

**Залежності:** `json`, `pathlib`

**Особливості реалізації:**
- Вирівнювання тільки по `id` (точний збіг) — без fuzzy-matching, без врахування відстані рядка
- `uk_by_id` як `dict` замість двох `list` — O(1) пошук замість O(n), критично для 218K записів
- 14 644 EN-only записів — рядки гри, локалізовані лише для EN (DLC-контент, технічні рядки)
- Порядок пар у `aligned` відповідає порядку EN-файлу — зручно для порівняння версій

**Час виконання:** ~3–5 секунд

---

### 4.3 classify.py

**Призначення:** Призначення одного з 7 семантичних типів кожному запису на основі евристик по EN-тексту. Класифікація за EN забезпечує незалежність від якості людського перекладу.

**Вхідні файли:**
- `data/intermediate/aligned.jsonl`

**Вихідні файли:**
- `data/intermediate/classified.jsonl` (додає `metadata.type`, `metadata.uk_human_quality`)

**Ключові функції:**

```python
classify(en: str) -> str
```
Застосовує 7 евристик за пріоритетом (перша що спрацювала — перемагає). Повертає один з: `"telepathic"`, `"narrative"`, `"ui_keybind"`, `"book_or_document"`, `"mechanic_description"`, `"ui_short"`, `"dialogue"`.

```python
_is_book_bracket(stripped: str) -> bool
```
Допоміжна: перевіряє, чи вміст першої пари `[...]` є змістовним описом (довжина ≥10, є пробіл і мала літера, не є числом), а не технічним ідентифікатором. Відрізняє `[This is a tome about...]` від `[GEN_FUNCTION_123]`.

**7 евристик за пріоритетом:**

| Пріоритет | Тип | Правило |
|-----------|-----|---------|
| 1 | `telepathic` | EN починається з `((*` |
| 2 | `narrative` | EN починається з `*` І закінчується на `*` (len ≥ 3) |
| 3 | `ui_keybind` | regex `^\[(IE_\|GLO_\|GEN_)` |
| 4 | `book_or_document` | починається з `[` і `_is_book_bracket()` == True |
| 5 | `mechanic_description` | regex `<LSTag` (case-insensitive) |
| 6 | `ui_short` | довжина < 30 І не закінчується на `.?!:)]["»…—-` |
| 7 | `dialogue` | fallback |

**Залежності:** `re`, `json`, `collections`

**Особливості реалізації:**
- `MARKER_MISMATCH_IDS: frozenset` — 3 hardcoded id записів з дефектним UK-маркером (виявлені вручну через `check_telepathic_uk.py`), отримують `uk_human_quality="marker_mismatch"` і виключаються з валідації
- Регулярні вирази скомпільовані на рівні модуля (`PUNCT_END_RE`, `LSTAG_RE` тощо) — одноразова компіляція для 218K ітерацій
- `BRACKET_ID_RE` визначений але не використовується у `classify()` — використовується `_is_book_bracket()` для точнішого розрізнення книжкового опису від GUID

**Час виконання:** ~5–8 секунд

---

### 4.4 filter.py

**Призначення:** Очищення і збагачення корпусу перед Gemini-перекладом. Чотири послідовних операції: стрип хвостових тегів, видалення порожніх, дедуплікація, обрахунок metadata.

**Вхідні файли:**
- `data/intermediate/classified.jsonl`

**Вихідні файли:**
- `data/intermediate/filtered.jsonl` (186 311 записів)

**Ключові функції:**

```python
strip_tail(text: str) -> str
```
Видаляє один або кілька `<br>` (всі варіанти: `<br>`, `<br/>`, `<BR>`) і trailing whitespace з кінця рядка. Regex: `(\s*<br\s*/?>)+\s*$`. Теги всередині рядка не чіпає.

```python
length_class(n: int) -> str
```
Визначає клас довжини: `"short"` (<100 символів), `"medium"` (100–499), `"long"` (500–2000), `"extreme"` (>2000).

```python
tag_counts(text: str) -> dict[str, int]
```
Підраховує кількість тегів `LSTag`, `i`, `b`, `br` у тексті за regex. Повертає `{"LSTag": int, "i": int, "b": int, "br": int}`.

```python
build_metadata(rec: dict, en_clean: str, uk_clean: str) -> dict
```
Будує повний словник metadata: тип, довжина, символьний підрахунок, наявність тегів, `tag_asymmetry` і деталі. Копіює `type` і `uk_human_quality` з попереднього кроку.

```python
run(in_path: Path, out_path: Path) -> tuple[list[dict], int, int, int]
```
Основна функція: послідовно виконує strip → фільтрацію порожніх → дедуплікацію → build_metadata. Повертає `(records, total_in, empty_count, dup_removed)`.

**Залежності:** `re`, `json`, `collections`

**Особливості реалізації:**
- Дедуплікація по парі `(en, uk_human)` після strip — зберігає варіанти перекладу одного EN-тексту якщо вони різні (напр. різні NPС з різними перекладами одного рядка)
- `_dup_count` тимчасовий ключ у записі під час обробки, видаляється у фінальному `build_metadata`
- `seen: dict[tuple, int]` зберігає індекс першого екземпляра у `deduped` — O(1) lookup і можливість оновлення лічильника без пошуку по списку
- 31 919 видалено дублікатів (17.1% від вирівняних пар) — ефект масового повторення коротких рядків типу "Yes.", "I see.", "Goodbye."

**Час виконання:** ~10–15 секунд

---

### 4.5 gemini.py

**Призначення:** Автоматичний переклад стратифікованої вибірки через Google Gemini API. Підтримує resume між сесіями, диференційовану обробку помилок, інкрементальне збереження.

**Вхідні файли:**
- `data/intermediate/sample.jsonl` (4 992 записи, генерується окремим скриптом `src/make_sample.py`)
- `prompts/gemini_v1.txt` — шаблон промпта

**Вихідні файли:**
- `data/intermediate/gemini_results.jsonl` (4 992 перекладів, накопичується через кілька сесій)
- `logs/gemini_run.log` — журнал усіх сесій

**Ключові функції:**

```python
init_client() -> genai.Client
```
Зчитує `GEMINI_API_KEY` з `.env` через `python-dotenv`. Явний шлях до `.env` через `Path(__file__).parent.parent / ".env"` — незалежно від поточної директорії при запуску. Кидає `RuntimeError` якщо ключ відсутній.

```python
load_done_ids(results_path: Path) -> set[str]
```
Читає `gemini_results.jsonl`, повертає set id з `uk_gemini != null`. **Побічний ефект:** якщо виявлені рядки з `uk_gemini=null` (FAIL з попередніх сесій) — перезаписує файл тільки OK-рядками. Забезпечує чистий resume без дублікатів.

```python
build_user_message(template: str, en_text: str, rec_type: str) -> str
```
Підставляє `{type}` і `{en_text}` у шаблон промпта.

```python
_call_api(client, user_message: str) -> str
```
Декорований `@retry(tenacity)`. Надсилає один запит до `gemini-3.1-flash-lite`. При виключенні класифікує помилку на `RetryableError` (429, 5xx) або `FatalError` (400, 403). `RetryableError` → exponential backoff 1→2→4→8→16→32 с, 6 спроб. `FatalError` → підіймається без повторів.

```python
translate_one(client, template: str, rec: dict) -> str | None
```
Обгортка навколо `_call_api`. Повертає рядок перекладу або `None` при будь-якому збої. Логує без значення API-ключа.

```python
run(sample_path, results_path, limit=None) -> None
```
Основний цикл: фільтрує вже перекладені через `load_done_ids`, ітерує по черзі (`pending`), зберігає кожен результат (`f.flush()` після кожного запису), засинає `SLEEP_BETWEEN=4.5с` між запитами. `limit` — обмеження для тестових прогонів.

**Залежності:** `google-genai`, `python-dotenv`, `tenacity`, `json`, `time`, `pathlib`, `argparse`

**Особливості реалізації:**
- Безкоштовний tier Gemini API: 500 RPD / 15 RPM → ~490 нових перекладів за сесію
- `SLEEP_BETWEEN=4.5с` — безпечний інтервал для 15 RPM (4.5 × 15 = 67.5с, але фактичне обмеження по RPM перевіряється сервером)
- Двостороннє логування: `StreamHandler` (консоль) + `FileHandler` (logs/gemini_run.log) — незалежні потоки, лог зберігається навіть при закритті термінала
- Rolling 24h window для денного ліміту (500 RPD) — скидається ~о 16:30–17:30 за київським часом (13:30–14:30 UTC) відповідно до спостережень
- Аргумент `--limit N` для поетапного тестування: `--limit 10` → `--limit 100` → повний прогін

**Час виконання:** ~6.2 год на 4 992 записи (4.5с × 4 992 + backoff), фактично ~10 сесій по ~490 записів (~10 днів з урахуванням денного ліміту)

---

### 4.6 build.py

**Призначення:** Збирає фінальний корпус `corpus.jsonl` з двох джерел: `filtered.jsonl` (всі 186 311 пар) і `gemini_results.jsonl` (4 992 переклади). Додає поле `metadata.in_sample`.

**Вхідні файли:**
- `data/intermediate/filtered.jsonl`
- `data/intermediate/gemini_results.jsonl`

**Вихідні файли:**
- `data/corpus.jsonl` (186 311 записів)

**Ключові функції:**

```python
load_gemini_index(path: Path) -> dict[str, str | None]
```
Читає `gemini_results.jsonl` і повертає `{id: uk_gemini}`. При дублікатах id останній перезаписує попередній (не виникало на практиці).

```python
run(filtered_path, gemini_path, corpus_path) -> None
```
Ітерує по `filtered`, для кожного запису шукає id у `gemini_index`. Три гілки: `in_sample=True + uk_gemini != null` → переклад є; `in_sample=True + uk_gemini=null` → FAIL (0 таких після ручних правок); `in_sample=False` → поза вибіркою. Зберігає у `corpus_path` у форматі фінальної схеми.

**Залежності:** `json`, `pathlib`, `logging`

**Особливості реалізації:**
- `in_sample` зберігається в metadata — дозволяє всім наступним модулям ізолювати вибірку без зовнішнього JOIN по `gemini_results.jsonl`
- Порядок записів у `corpus.jsonl` відповідає `filtered.jsonl` — детерміновано через `seed=42` у `make_sample.py`

**Час виконання:** ~15–25 секунд

---

### 4.7 stats.py

**Призначення:** Генерує описову статистику корпусу у вигляді Markdown-таблиць для Розділу 4 дипломної роботи.

**Вхідні файли:**
- `data/corpus.jsonl`

**Вихідні файли:**
- `data/stats.md` (7 розділів статистики)

**Ключові функції:**

```python
tokenize(text: str) -> list[str]
```
Whitespace-токенізація (`text.split()`). Достатня для порівняльної токенної статистики без потреби у stanza/mystem для українського.

```python
tok_stats(counts: list[int]) -> dict
```
Обчислює `{"mean", "median", "p95", "min", "max"}` для списку підрахунків токенів.

```python
percentile(data: list[float], p: float) -> float
```
P-й перцентиль методом прямого індексування (`int(len * p / 100)`).

```python
run(corpus_path, out_path) -> None
```
Проходить по корпусу один раз, накопичує: `Counter` типів, `Counter` length_class, списки довжин токенів для EN/uk_human/uk_gemini, підрахунки тегів і асиметрій по класах. Формує Markdown-рядки через `list.append()` і записує файл.

**Залежності:** `json`, `statistics`, `collections`, `pathlib`

**Час виконання:** ~20–30 секунд

---

### 4.8 validate.py

**Призначення:** Обчислення п'яти MT-метрик якості перекладу (`uk_gemini` vs `uk_human`) в трьох групуваннях: aggregate, по 7 типах тексту, tag_asymmetry.

**Вхідні файли:**
- `data/corpus.jsonl`

**Вихідні файли:**
- `data/validation_results.md` — таблиці метрик
- `data/validation_raw.jsonl` — per-record дані з `bertscore_f1`

**Ключові функції:**

```python
strip_tags(text: str) -> str
```
Видаляє теги `<...>` через regex `<[^>]+>`. Зберігає плейсхолдери `[1]`, маркери `*...*` і `((*...*))`. Застосовується до обох сторін порівняння перед обчисленням метрик.

```python
compute_sacrebleu_metrics(hyps: list[str], refs: list[str]) -> dict
```
Обчислює BLEU (`sacrebleu.corpus_bleu`, tokenize='13a'), TER (`sacrebleu.corpus_ter`), ChrF++ (`sacrebleu.corpus_chrf`, word_order=2). METEOR — через NLTK `meteor_score` з `word_tokenize(text.lower())` (оскільки `sacrebleu.corpus_meteor` видалено у sacrebleu 2.x). Повертає `{"BLEU", "METEOR", "TER", "CHRF", "n"}`.

```python
compute_bertscore(hyps, refs, model) -> dict
```
BERTScore P/R/F1 через `bert_score.score()`. Модель `xlm-roberta-base` (~500 MB, кешується локально після першого завантаження). Повертає середні значення × 100.

```python
run(corpus_path, results_md, results_jsonl) -> None
```
Основна функція: завантаження і фільтрація (тільки `in_sample=True` і `uk_gemini != null`, виключення `marker_mismatch`), strip тегів, одноразовий BERTScore для всієї вибірки (per-record значення зберігаються в `r["_bs_f1"]`), обчислення sacrebleu по групах, формування Markdown і JSONL виводу.

**Залежності:** `sacrebleu`, `bert-score`, `torch`, `nltk`, `json`, `re`, `collections`, `pathlib`

**Особливості реалізації:**
- BERTScore обчислюється **один раз** для всієї вибірки (один batch), per-record результати зберігаються в записах як `r["_bs_f1"]`. Групові значення обчислюються підсумовуванням відповідних per-record значень — замість повторного запуску моделі для кожної групи
- `device=None` у `bert_score.score()` → автоматичний вибір CPU/GPU. На CPU (~4.99 GB RAM, Intel i5) займає ~11 хвилин для 4 990 пар
- Перше завантаження `xlm-roberta-base` (~500 MB) зберігається у кеші `~/.cache/huggingface/` — наступні запуски без завантаження

**Час виконання:** ~15 хвилин (перший запуск з завантаженням моделі), ~11 хвилин (з кешем)

---

## 5. Промпт (gemini_v1.txt)

Шаблон промпта (версія 3, фінальна). Підставляються два плейсхолдери: `{type}` і `{en_text}`.

**Ключові правила промпта:**
1. Виводити ТІЛЬКИ переклад — без пояснень і лапок
2. Зберігати теги `<i>`, `<b>`, `<br>`, `<LSTag>`, плейсхолдери `[1]`, маркери `*` і `((*`
3. Транслітерація власних імен у Cyrillic (Halsin → Гальсін), але не семантичний переклад
4. Різний регістр по типах: `dialogue` → «ти», `narrative` → «ви», `telepathic` → «ти» + фрагментарний стиль, `ui_short`/`ui_keybind` → називний відмінок, `mechanic_description` → нейтральний третя особа, `book_or_document` → відповідний регістр першоджерела
5. Збереження квадратних дужок-префіксів у `book_or_document`
6. Темне фентезі: де доречно — архаїзований лексикон, але не надмірно

**Ітерації промпта:**
- **v1:** Базові правила, без прикладів транслітерації → власні імена залишалися латиницею
- **v2:** Додано приклади транслітерації (Halsin → Гальсін), виправлено «ви»→«ти» для telepathic → тепер «ти» для telepathic і «ви» для narrative
- **v3 (фінал):** Додано збереження `[...]`-префіксів у book_or_document

---

## 6. Технічний стек

| Бібліотека | Версія | Роль |
|-----------|--------|------|
| Python | ≥ 3.11 | Основна мова |
| `lxml` | 5.3.1 | Ітеративний парсинг XML (iterparse) |
| `python-dotenv` | 1.2.2 | Завантаження `.env` |
| `google-genai` | 2.3.0 | Google Gemini SDK (`from google import genai`) |
| `tenacity` | 9.1.4 | Exponential backoff для retry |
| `nltk` | 3.9.1 | `word_tokenize`, `meteor_score` |
| `sacrebleu` | ≥ 2.4.0 | BLEU, TER, ChrF++ |
| `bert-score` | ≥ 0.3.13 | BERTScore (xlm-roberta-base) |
| `torch` | 2.6.0 | Залежність bert-score |

**Примітка щодо `google-genai`:** Стара бібліотека `google-generativeai` є deprecated з 2026; новий SDK — `google-genai` (import `from google import genai`). Версії несумісні.

**Примітка щодо `sacrebleu` і METEOR:** У sacrebleu 2.x функція `corpus_meteor` видалена. METEOR обчислюється через NLTK `nltk.translate.meteor_score.meteor_score` з `word_tokenize(text.lower())` для токенізації.

---

## 7. Відомі обмеження і технічні рішення

### 7.1 Один референс vs. множина варіантів
Всі метрики (BLEU, METEOR, TER, ChrF++, BERTScore) обчислюються з одним референсом (`uk_human`). Офіційний переклад сам містить стилістичні варіанти і спрощення — це штрафує Gemini за правильні, але відмінні переклади. Особливо помітно в `mechanic_description`, де людський перекладач скорочував тексти.

### 7.2 BERTScore і мова
`xlm-roberta-base` підтримує українську, але не спеціалізована модель для UA. Для вищої точності можна використати `lang-uk/roberta-base-ukrainian`, але вона потребує більше RAM і часу.

### 7.3 BLEU і короткі рядки
82.7% корпусу — `short` (<100 символів). BLEU нестабільний на коротких рядках через brevity penalty і малу кількість n-грамів. METEOR і BERTScore надійніші для цих класів.

### 7.4 Daily limit і resume
500 RPD обмеження — rolling 24h window, не calendar day. `load_done_ids()` автоматично видаляє FAIL-рядки при resume, що дозволяє відновлення без ручного редагування файлів після кожної сесії.

### 7.5 Дедуплікація по парі (en, uk)
Дедуплікація по `(en, uk_human)` замість тільки по `en` — зберігає ситуації де один EN-рядок має різні UK-переклади у різних NPC. 4 такі пари виявлені в корпусі; вони лінгвістично цінніші за типові дублікати.
