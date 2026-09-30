"""friday · tests/evals/conftest.py

The Anthropic client is cached module-wide (adapters/llm.py) and binds to the
event loop that first used it; pytest gives each async test a fresh loop, so
reset the cache between eval tests or the second file dies on a closed loop.
"""

import pytest

import adapters.llm as llm


@pytest.fixture(autouse=True)
def _fresh_llm_client():
    llm._client = None
    yield
    llm._client = None
