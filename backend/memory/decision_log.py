# PIP Memory layer - Decision Log
#
# Query Constraints:
# - active_projects queries must go as a direct DB query, never cached.
# - decision_text field is write-once, state is the only mutable field.
# (Enforced both by triggers in schema.sql and query layout).
