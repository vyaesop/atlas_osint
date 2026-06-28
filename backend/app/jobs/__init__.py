"""Background-job layer.

Write paths call the :mod:`app.jobs.dispatch` helpers. With ``JOBS_ENABLED``
false (default) they run inline, exactly as before; with it true they enqueue
to an arq/Redis queue drained by :mod:`app.jobs.worker`, taking graph
projection, search indexing, and ingestion off the request path for scale.
"""
