"""Search subsystem.

Pluggable behind :class:`~app.search.backend.SearchBackend`:

* ``inmemory`` — pure-Python, used in dev/tests; supports full-text, fuzzy,
  alias matching and semantic (embedding cosine) ranking with no dependencies.
* ``opensearch`` — production backend using a text + kNN-vector index.

The active backend is chosen by ``settings.SEARCH_BACKEND`` and exposed as the
``search_service`` singleton from :mod:`app.search.service`.
"""
