# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
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
