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

# Supabase credentials are read at import time by db/supabase_manager.py
# and career_recommendation/ingestion.py. Dummy values keep those imports
# working; no test opens a real connection.
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-dummy-service-key")
os.environ.setdefault("SUPABASE_DB_URL", "postgresql://test:test@localhost:5432/test")

# --- Stub out heavy optional dependencies so these tests can run without
# installing sentence-transformers / torch / the Supabase client. They are
# only needed at import time by services.llm_client and db.supabase_manager;
# unit tests here never call the real classes.
for _mod_name, _attrs in [
    ("langchain_google_genai", ["GoogleGenerativeAIEmbeddings", "ChatGoogleGenerativeAI"]),
    ("langchain_huggingface", ["HuggingFaceEmbeddings"]),
    ("langchain_community.vectorstores", ["SupabaseVectorStore"]),
    ("supabase.client", ["create_client", "Client"]),
]:
    if _mod_name not in sys.modules:
        stub = types.ModuleType(_mod_name)
        for _attr in _attrs:
            setattr(stub, _attr, MagicMock())
        sys.modules[_mod_name] = stub

        # A dotted stub also needs its parent package registered, and the
        # child bound onto it, or `from parent.child import X` fails.
        if "." in _mod_name:
            _parent_name, _child_name = _mod_name.rsplit(".", 1)
            if _parent_name not in sys.modules:
                _parent = types.ModuleType(_parent_name)
                _parent.__path__ = []  # mark as a package
                sys.modules[_parent_name] = _parent
            setattr(sys.modules[_parent_name], _child_name, stub)