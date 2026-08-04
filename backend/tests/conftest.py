"""
core.config.GlobalConfig raises at import time if GOOGLE_API_KEY isn't
set (see src/core/config.py). None of the tests under this directory
make a real API call, so a dummy value is enough to let the module
import cleanly in CI / on a machine with no .env configured.

This must run before ANY of this repo's modules are imported, hence
setting it here in conftest.py rather than in an individual test file.
"""

import os
import sys
import types
from unittest.mock import MagicMock

os.environ.setdefault("GOOGLE_API_KEY", "test-dummy-key-not-a-real-credential")
os.environ.setdefault("EMBEDDING_PROVIDER", "huggingface")

# --- Stub out heavy optional ML dependencies (langchain-google-genai,
# langchain-huggingface, langchain-chroma) so these tests can run
# without installing sentence-transformers/torch/etc. They are only
# needed at import time by services.llm_client / db.chroma_manager;
# unit tests here never call the real classes.
for _mod_name, _attrs in [
    ("langchain_google_genai", ["GoogleGenerativeAIEmbeddings", "ChatGoogleGenerativeAI"]),
    ("langchain_huggingface", ["HuggingFaceEmbeddings"]),
    ("langchain_chroma", ["Chroma"]),
]:
    if _mod_name not in sys.modules:
        stub = types.ModuleType(_mod_name)
        for _attr in _attrs:
            setattr(stub, _attr, MagicMock())
        sys.modules[_mod_name] = stub
