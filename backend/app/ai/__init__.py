"""AI-assisted extraction and summarization.

LLMs are assistants only: everything produced here is labeled AI-generated and
unverified until a researcher confirms it (the Phase 2 verification workflow).

Pluggable behind :class:`~app.ai.provider.ExtractionProvider`:

* ``heuristic`` — default. Rule/regex-based, dependency-free, fully local, no
  API key. Lower recall than an LLM but deterministic and private.
* ``anthropic`` — Claude-powered (``claude-opus-4-8``) via the Anthropic SDK
  with structured outputs. Activated by ``AI_PROVIDER=anthropic`` + a key.
"""
