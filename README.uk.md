[English](README.md) | **Українська**
# bg3-corpus — Паралельний корпус EN-UK на основі текстів Baldur's Gate 3

Пайплайн для побудови паралельного англійсько-українського корпусу з текстів локалізації Baldur's Gate 3, з автоматичним перекладом через Google Gemini API та обчисленням MT-метрик якості.

Практична частина дипломної роботи **«Створення поліфункціонального паралельного англо-українського корпусу текстів на основі контенту відеоігор»** — Київський національний університет імені Тараса Шевченка, 2026.

---

## Посилання на матеріали

| Ресурс | Посилання |
|--------|-----------|
| **Код пайплайну (цей репозиторій)** | https://github.com/ZavarOvek/crispy_invention |
| **Корпус і результати (Google Drive)** | https://drive.google.com/drive/folders/1PHGYLNj4pqAisXkIUog3smQXU3fxoZIZ?usp=sharing |

> Корпус розміщено на Google Drive через великий розмір файлів (~120 MB).

---

## Результати (травень 2026)

| Метрика | Значення |
|---------|---------|
| Всього пар у корпусі | **186 311** |
| Стратифікована вибірка для Gemini | 4 992 |
| Перекладено Gemini | 4 992 (100%) |
| BLEU (aggregate) | 23.16 |
| METEOR | 49.57 |
| TER | 73.16 |
| ChrF++ | 46.75 |
| **BERTScore F1** | **91.93** |

### Метрики по типах тексту

| Тип | n | BLEU | METEOR | TER | ChrF++ | BERTScore F1 |
|-----|---|------|--------|-----|--------|-------------|
| `dialogue` | 2 500 | 23.26 | 50.42 | 73.25 | 45.89 | 92.15 |
| `ui_short` | 700 | 22.76 | 36.96 | 60.79 | 47.29 | 90.70 |
| `narrative` | 800 | 23.81 | 56.05 | 73.59 | 46.28 | 92.75 |
| `mechanic_description` | 600 | 19.50 | 46.58 | 77.89 | 44.23 | 90.92 |
| `book_or_document` | 200 | 21.61 | 46.64 | 72.66 | 48.53 | 91.41 |
| `telepathic` | 98 | 39.72 | 73.76 | 67.11 | 49.45 | 93.46 |
| `ui_keybind` | 92 | 49.81 | 66.36 | 48.96 | 64.53 | 94.11 |

---

## Архітектура пайплайну

```
Localization/
  english.loca.xml   ──┐
  ukrainian.loca.xml ──┘
          │
          ▼  src/extract.py        XML → JSONL (232 876 + 218 232 записів)
          ▼  src/align.py          вирівнювання за contentuid → 218 232 пар
          ▼  src/classify.py       7 семантичних типів
          ▼  src/filter.py         дедуплікація (-31 919) + metadata → 186 311
          ▼  src/make_sample.py    стратифікована вибірка 4 992 (seed=42)
          ▼  src/gemini.py         Gemini API переклад → gemini_results.jsonl
          ▼  src/build.py          збірка → corpus.jsonl
          ├──▶ src/stats.py        → stats.md
          └──▶ src/validate.py     → validation_results.md + validation_raw.jsonl
```

Повна технічна документація: [TECHNICAL.md](TECHNICAL.md)

---

## 7 типів тексту

| Тип | Евристика | Приклад |
|-----|-----------|---------|
| `dialogue` | fallback | "I'll help you find it." |
| `narrative` | `*...*` | `*The door swings open.*` |
| `telepathic` | `((*...*))` | `((*flesh-walker, tongue-talker*))` |
| `mechanic_description` | містить `<LSTag` | "Deals 1d4 Poison damage..." |
| `book_or_document` | `[Описовий префікс...]` | "[A tattered journal entry.]" |
| `ui_short` | довжина <30, без пунктуації | "Attack", "Cancel" |
| `ui_keybind` | починається з `[GLO_`, `[GEN_`, `[IE_` | "[GLO_Action_...]" |

---

## Встановлення

```bash
# Python 3.11+
pip install -r requirements.txt
python -m nltk.downloader punkt wordnet averaged_perceptron_tagger

# Ключ Gemini API
echo "GEMINI_API_KEY=your_key_here" > .env
```

Потрібні XML-файли локалізації з легально придбаної копії BG3:
```
Localization/
  english.loca.xml
  ukrainian.loca.xml
```

---

## Запуск

```bash
# Кроки 1-4: побудова корпусу (~2-3 хвилини)
python src/extract.py
python src/align.py
python src/classify.py
python src/filter.py
python src/make_sample.py   # стратифікована вибірка 4 992 записів

# Крок 5: Gemini-переклад (запускати щодня, resume автоматичний)
python src/gemini.py              # повний прогін
python src/gemini.py --limit 10   # тест: 10 записів

# Кроки 6-8: збірка і метрики
python src/build.py
python src/stats.py
python src/validate.py
```

> **Увага щодо Gemini API:** Безкоштовний tier — 500 запитів/добу. Повний переклад 4 992 записів займає ~10 сесій (~10 днів). `gemini.py` автоматично відновлюється з місця зупинки.

---

## Вміст репозиторію

```
bg3-corpus/
├── src/
│   ├── scout_tags.py          # розвідка структури XML (одноразово)
│   ├── extract.py             # XML → JSONL
│   ├── align.py               # вирівнювання EN-UK
│   ├── classify.py            # класифікація 7 типів
│   ├── filter.py              # дедуплікація + metadata
│   ├── make_sample.py         # стратифікована вибірка
│   ├── gemini.py              # Gemini API переклад
│   ├── build.py               # збірка corpus.jsonl
│   ├── stats.py               # описова статистика
│   └── validate.py            # MT-метрики
├── prompts/
│   └── gemini_v1.txt          # промпт (v3, фінальний)
├── examples/                  # ілюстративні вибірки (10-20 записів/тип)
├── TECHNICAL.md               # повна технічна документація
├── requirements.txt
├── LICENSE                    # MIT для коду; дані — окремо
└── README.md
```

**Корпус і результати** (corpus.jsonl, validation_raw.jsonl, stats.md тощо) — на [Google Drive](https://drive.google.com/drive/folders/1PHGYLNj4pqAisXkIUog3smQXU3fxoZIZ?usp=sharing).

---

## Цитування

```bibtex
@thesis{bg3corpus2026,
  author = {Karmana},
  title  = {Створення поліфункціонального паралельного англо-українського
            корпусу текстів на основі контенту відеоігор},
  school = {Київський національний університет імені Тараса Шевченка},
  year   = {2026},
  type   = {Бакалаврська робота},
  url    = {https://github.com/ZavarOvek/crispy_invention}
}
```

---

## Ліцензія

Код пайплайну: **MIT**. Детальніше: [LICENSE](LICENSE).

Тексти корпусу є інтелектуальною власністю Larian Studios і використовуються виключно в академічних цілях (fair use). Повний корпус не розповсюджується.
