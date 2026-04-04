"""Tests for Procrastinate schema bootstrapping (TQ-04)."""
import pytest


@pytest.mark.xfail(reason="Wave 0 stub — implementation in Task 2")
def test_procrastinate_schema_namespace_exists():
    """The 'procrastinate' PostgreSQL schema is created at startup."""
    # Requires database connection — tested after lifespan runs
    assert False, "Needs database integration test"


@pytest.mark.xfail(reason="Wave 0 stub — implementation in Task 2")
def test_procrastinate_jobs_table_exists():
    """Procrastinate's procrastinate_jobs table exists after apply_schema."""
    assert False, "Needs database integration test"
