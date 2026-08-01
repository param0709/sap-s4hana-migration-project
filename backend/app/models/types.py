"""Portable column types.

The runtime database is PostgreSQL; the test-suite runs on SQLite. These
variants let a single model definition serve both without dialect-specific code
leaking into the models themselves.
"""
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, plain JSON everywhere else.
JSONType = JSON().with_variant(JSONB(), "postgresql")
