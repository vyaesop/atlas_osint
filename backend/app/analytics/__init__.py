"""Analytics subsystem: centrality, community detection, and path discovery.

Pluggable behind :class:`~app.analytics.backend.AnalyticsBackend`:

* ``networkx`` — default. Loads the graph from PostgreSQL (source of truth) and
  computes locally; zero external services, ideal for local-first deployments.
* ``neo4j_gds`` — future. Offloads to Neo4j Graph Data Science for very large
  graphs (Phase 6 scaling).

Selected by ``settings.ANALYTICS_BACKEND`` and exposed as ``analytics_service``.
"""
