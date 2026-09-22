"""Pure functions of the offline pipeline stages (no XML, no network)."""

from __future__ import annotations

import json

import pytest

import align
import build
import filter as filter_stage

# ---------------- filter ----------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello<br>", "Hello"),
        ("Hello<br/><BR />  ", "Hello"),
        ("Hello <br> world<br>", "Hello <br> world"),
        ("   ", ""),
    ],
)
def test_strip_tail_removes_only_trailing_breaks(text, expected):
    assert filter_stage.strip_tail(text) == expected


@pytest.mark.parametrize(
    ("n", "cls"),
    [
        (0, "short"),
        (99, "short"),
        (100, "medium"),
        (499, "medium"),
        (500, "long"),
        (2000, "long"),
        (2001, "extreme"),
    ],
)
def test_length_class_boundaries(n, cls):
    assert filter_stage.length_class(n) == cls


def test_tag_counts():
    text = '<LSTag Tooltip="x">Word</LSTag> <i>a</i> <b>b</b><br>'
    assert filter_stage.tag_counts(text) == {"LSTag": 2, "i": 2, "b": 2, "br": 1}


def test_build_metadata_flags_tag_asymmetry():
    meta = filter_stage.build_metadata(
        {"metadata": {"type": "dialogue"}}, "<i>Hi</i> [1]", "Привіт [1]"
    )
    assert meta["type"] == "dialogue"
    assert meta["has_italic"] is True
    assert meta["has_placeholder"] is True
    assert meta["tag_asymmetry"] is True
    assert meta["tag_asymmetry_details"] == {"i": [2, 0]}


def test_filter_run_strips_drops_empty_and_counts_duplicates(tmp_path):
    rows = [
        {"id": "a", "version": 1, "en": "Hi<br>", "uk_human": "Привіт", "metadata": {}},
        {"id": "b", "version": 1, "en": "Hi", "uk_human": "Привіт<br>", "metadata": {}},
        {"id": "c", "version": 1, "en": "<br>", "uk_human": "Щось", "metadata": {}},
    ]
    src = tmp_path / "classified.jsonl"
    src.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    final, total_in, empty, dups = filter_stage.run(src, tmp_path / "filtered.jsonl")
    assert (total_in, empty, dups) == (3, 1, 1)
    assert [r["id"] for r in final] == ["a"]
    assert final[0]["metadata"]["duplicate_count"] == 2


# ---------------- align ----------------


def test_align_pairs_by_id_and_reports_en_only():
    en = [{"id": "h1", "version": 1, "text": "One"}, {"id": "h2", "version": 1, "text": "Two"}]
    uk = [{"id": "h1", "version": 1, "text": "Один"}]
    aligned, en_only = align.align(en, uk)
    assert aligned == [{"id": "h1", "version": 1, "en": "One", "uk_human": "Один"}]
    assert en_only == [{"id": "h2", "version": 1, "text": "Two", "reason": "no_uk_translation"}]


# ---------------- build ----------------


def test_build_marks_sample_membership(tmp_path):
    filtered = tmp_path / "filtered.jsonl"
    rows = [
        {"id": i, "version": 1, "en": "e", "uk_human": "u", "metadata": {"type": "dialogue"}}
        for i in ("in_ok", "in_fail", "out")
    ]
    filtered.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    gemini_results = tmp_path / "gemini.jsonl"
    gemini_results.write_text(
        json.dumps({"id": "in_ok", "uk_gemini": "г"})
        + "\n"
        + json.dumps({"id": "in_fail", "uk_gemini": None})
        + "\n",
        encoding="utf-8",
    )
    corpus = tmp_path / "corpus.jsonl"
    build.run(filtered, gemini_results, corpus)
    out = {r["id"]: r for r in map(json.loads, corpus.read_text(encoding="utf-8").splitlines())}
    assert out["in_ok"]["uk_gemini"] == "г" and out["in_ok"]["metadata"]["in_sample"] is True
    assert out["in_fail"]["uk_gemini"] is None and out["in_fail"]["metadata"]["in_sample"] is True
    assert out["out"]["uk_gemini"] is None and out["out"]["metadata"]["in_sample"] is False
