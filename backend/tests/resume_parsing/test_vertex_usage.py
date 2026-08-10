from types import SimpleNamespace

from src.resume_parsing.internal.providers.vertex_ai import VertexAIResumeProvider


def provider_without_client() -> VertexAIResumeProvider:
    provider = object.__new__(VertexAIResumeProvider)
    provider._usage_events = []
    return provider


def test_records_google_usage_metadata() -> None:
    provider = provider_without_client()
    response = SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=120,
        candidates_token_count=30,
        total_token_count=150,
        cached_content_token_count=20,
        thoughts_token_count=None,
    ))

    provider._record_genai_usage(response, page_index=2, model="gemini")

    assert provider.drain_usage() == [{
        "model": "gemini", "page_index": 2, "prompt_tokens": 120,
        "output_tokens": 30, "total_tokens": 150, "cached_input_tokens": 20,
        "thinking_tokens": None, "source": "google_genai_usage_metadata",
    }]
    assert provider.drain_usage() == []


def test_records_openai_compatible_usage_metadata() -> None:
    provider = provider_without_client()
    response = SimpleNamespace(usage=SimpleNamespace(
        prompt_tokens=200,
        completion_tokens=50,
        total_tokens=250,
        prompt_tokens_details=SimpleNamespace(cached_tokens=10),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=5),
    ))

    provider._record_openai_usage(response, page_index=0, model="gemma-maas")

    assert provider.drain_usage()[0] == {
        "model": "gemma-maas", "page_index": 0, "prompt_tokens": 200,
        "output_tokens": 50, "total_tokens": 250, "cached_input_tokens": 10,
        "thinking_tokens": 5, "source": "vertex_openai_usage",
    }
