# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- `README.md`, `README.uk.md`, `TECHNICAL.md`: the NLTK download step now also
  fetches `punkt_tab`; NLTK >= 3.9 (what `nltk>=3.8.0` installs) no longer
  finds `punkt` for `word_tokenize`, so `src/validate.py` failed with a
  `LookupError` on a fresh setup.
- `src/gemini.py`: a fatal API error (400/401/403/404, e.g. an invalid key)
  now stops the whole run, as the module docstring always promised. It used
  to fail the record and move on, so a bad key meant one failed request per
  record, 4.5 s apart, for the entire sample.
- `src/gemini.py`: errors are classified by the HTTP `code` on the SDK
  exception first; the substring search on the message is only a fallback
  (a message mentioning "1500 tokens" used to read as a server error).
- `src/gemini.py`: an empty response (safety block, no candidates) fails that
  record once instead of being retried six times with backoff.
- `TECHNICAL.md`, `src/validate.py`: sacrebleu never implemented METEOR; the
  docs said it had been removed in 2.x. Dropped `pyproject.toml` from the
  file tree in `TECHNICAL.md`, the repository has none.
- `src/filter.py`: `run()` is annotated with the tuple it actually returns.

### Documentation
- METEOR caveat in both READMEs and `TECHNICAL.md` §7.6: NLTK's stemmer and
  WordNet are English-only, so on Ukrainian the score counts exact word-form
  matches. Published figures are unchanged.

### Added
- Tests (`tests/`, 28 cases): Gemini error handling against a fake client and
  a stubbed SDK, and the pure functions of `filter`, `align` and `build`.
  CI runs them on Python 3.11 and 3.12; `pytest.ini` puts `src/` on the path.
- GitHub Actions CI: a `ruff` lint job and an import smoke job on Python
  3.11 and 3.12. The smoke job installs only `lxml`; the heavy stack
  (`torch`, `bert-score`, `sacrebleu`, `nltk`, `google-genai`) lives solely
  in `validate.py` and `gemini.py` and never enters CI.
- Ruff configuration in `ruff.toml` (`RUF001-003` disabled: they flag
  Cyrillic letters as ambiguous look-alikes of Latin ones, which is a false
  positive in a Ukrainian-language project; `E501` left to the formatter).
- Status badges in both READMEs.

### Fixed
- `src/scout_tags.py`: dropped a leftover `full_tag` assignment that was
  never read.
- `src/stats.py`: removed an unused `re` import.
- `src/make_sample.py`: the module body now lives in `main()` behind an
  `if __name__ == "__main__"` guard, like every other stage. Importing it no
  longer reads `data/intermediate/filtered.jsonl` and no longer reseeds the
  global RNG as a side effect; `random.seed(42)` moved into `main()`.
  Outputs were verified byte-for-byte identical to the previous version on a
  synthetic 4,000-record fixture.
- `src/validate.py`: `zip()` over hypotheses and references is now explicit
  about `strict=True`. The two lists come from the same sample and have
  always matched in length, so results are unchanged; the invariant is now
  enforced rather than assumed.

### Changed
- `src/build.py`: renamed the ambiguous loop variable `l` to `line`.
- Adopted `ruff format`; the tree was reformatted in a single dedicated
  commit (see `.git-blame-ignore-revs`).
- `src/classify.py` and `src/gemini.py` carry explicit `noqa` directives with
  rationale instead of being restructured — `classify.py` produced the
  published type distribution and is deliberately left as is.

## [1.0.0] - 2026-05

Thesis submission state: the pipeline as defended at Taras Shevchenko
National University of Kyiv.

- EN-UK parallel corpus from Baldur's Gate 3 localization: 186,311 pairs.
- Stratified sample of 4,992 translated via the Google Gemini API.
- MT quality metrics: BLEU 23.16, METEOR 49.57, TER 73.16, ChrF++ 46.75,
  BERTScore F1 91.93, with a per-type breakdown across 7 semantic classes.
- Ten pipeline stages from XML extraction through alignment, classification,
  filtering, sampling, translation, assembly, statistics and validation.
