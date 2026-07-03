# PIP Memory layer - Vector Store (ChromaDB)
#
# Startup Rebuild Trigger:
# ChromaDB is NEVER authoritative. If ChromaDB drifts from SQLite (schema version mismatch
# or document list discrepancy), a startup rebuild-on-mismatch trigger is fired to
# clear ChromaDB and re-index from SQLite authoritative state.
