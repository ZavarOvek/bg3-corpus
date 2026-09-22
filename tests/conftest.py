"""Shared test setup.

`src/gemini.py` imports the `google-genai` SDK at module level. The tests
never talk to the API, so a minimal stub stands in for the SDK and CI does
not have to install it.
"""

from __future__ import annotations

import sys
import types


def _stub_google_genai() -> None:
    if "google.genai" in sys.modules:
        return
    google = sys.modules.get("google") or types.ModuleType("google")
    genai = types.ModuleType("google.genai")
    genai_types = types.ModuleType("google.genai.types")
    genai_types.GenerateContentConfig = lambda **kwargs: kwargs
    genai.types = genai_types
    genai.Client = object
    google.genai = genai
    sys.modules["google"] = google
    sys.modules["google.genai"] = genai
    sys.modules["google.genai.types"] = genai_types


_stub_google_genai()
