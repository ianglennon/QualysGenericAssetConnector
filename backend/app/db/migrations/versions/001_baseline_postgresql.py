"""Baseline PostgreSQL schema

Creates all application tables from scratch for PostgreSQL.
Replaces all previous incremental migrations with a single baseline.

Revision ID: 001_baseline
Revises: None
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users (no FKs) ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "operator", name="userrole"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("refresh_token", sa.String(), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- qualys_config (no FKs) ---
    op.create_table(
        "qualys_config",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("connector_uuid", sa.String(), nullable=False),
        sa.Column("encrypted_password", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- connectors (no FKs) ---
    op.create_table(
        "connectors",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("base_url", sa.String(), nullable=False),
        sa.Column("test_path", sa.String(), nullable=True),
        sa.Column("auth_method", sa.String(), nullable=False),
        sa.Column("encrypted_token", sa.String(), nullable=True),
        sa.Column("encrypted_username", sa.String(), nullable=True),
        sa.Column("encrypted_password", sa.String(), nullable=True),
        sa.Column("api_key_name", sa.String(), nullable=True),
        sa.Column("encrypted_api_key", sa.String(), nullable=True),
        sa.Column("source_retry_limit", sa.Integer(), nullable=True),
        sa.Column("qualys_retry_limit", sa.Integer(), nullable=True),
        sa.Column("cron_schedule", sa.String(), nullable=True),
        sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("execution_timeout", sa.Integer(), nullable=True),
        sa.Column("verify_ssl", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_valid_mappings", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("fault_diagnosis", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- connector_endpoints (FK to connectors) ---
    op.create_table(
        "connector_endpoints",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.String(),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("pagination_config", sa.JSON(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("data_root", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- canvases (FK to connectors) ---
    op.create_table(
        "canvases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.String(),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- canvas_endpoints (FK to canvases, connector_endpoints, self-ref) ---
    op.create_table(
        "canvas_endpoints",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "canvas_id",
            sa.String(),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "endpoint_id",
            sa.String(),
            sa.ForeignKey("connector_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_ref_id",
            sa.String(),
            sa.ForeignKey("canvas_endpoints.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field_role", sa.String(), nullable=False, server_default=sa.text("'data'")),
        sa.Column("variable_extractions", sa.JSON(), nullable=True),
        sa.Column("max_concurrency", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("exclusion_rules", sa.JSON(), nullable=True),
        sa.Column("tree_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # --- field_mappings (FK to connector_endpoints, canvases) ---
    op.create_table(
        "field_mappings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "endpoint_id",
            sa.String(),
            sa.ForeignKey("connector_endpoints.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "canvas_id",
            sa.String(),
            sa.ForeignKey("canvases.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("target_field", sa.String(), nullable=False),
        sa.Column("mapping_type", sa.String(), nullable=False),
        sa.Column("source_field", sa.String(), nullable=True),
        sa.Column("static_value", sa.String(), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=True),
        sa.Column("fallback", sa.String(), nullable=True),
        sa.Column("array_path", sa.String(), nullable=True),
        sa.Column("extract_field", sa.String(), nullable=True),
        sa.Column("collect_filter", sa.JSON(), nullable=True),
        sa.Column("separator", sa.String(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # --- run_history (FK to connectors) ---
    op.create_table(
        "run_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "connector_id",
            sa.String(),
            sa.ForeignKey("connectors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("running", "success", "partial_success", "failed", "skipped", name="runstatus"),
            nullable=False,
        ),
        sa.Column("triggered_by", sa.String(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_submitted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_type", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("error_context", sa.JSON(), nullable=True),
        sa.Column("source_api_calls", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("qualys_api_calls", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_run_history_connector_id", "run_history", ["connector_id"])

    # --- run_failures (FK to run_history) ---
    op.create_table(
        "run_failures",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("run_history.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("record_identifier", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_run_failures_run_id", "run_failures", ["run_id"])

    # --- endpoint_run_logs (FK to run_history, connector_endpoints) ---
    op.create_table(
        "endpoint_run_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("run_history.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "endpoint_id",
            sa.String(),
            sa.ForeignKey("connector_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("execution_order", sa.Integer(), nullable=False),
        sa.Column("records_fetched", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_submitted", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_failed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("records_filtered", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("failure_stage", sa.String(), nullable=True),
        sa.Column("http_request", sa.JSON(), nullable=True),
        sa.Column("http_response", sa.JSON(), nullable=True),
        sa.Column("canvas_id", sa.String(), nullable=True),
        sa.Column("source_api_calls", sa.Integer(), nullable=True, server_default=sa.text("0")),
        sa.Column("child_requests_total", sa.Integer(), nullable=True),
        sa.Column("child_requests_failed", sa.Integer(), nullable=True),
        sa.Column("child_requests_skipped", sa.Integer(), nullable=True),
        sa.Column("depth", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_endpoint_run_logs_run_id", "endpoint_run_logs", ["run_id"])
    op.create_index("ix_endpoint_run_logs_endpoint_id", "endpoint_run_logs", ["endpoint_id"])

    # --- run_events (FK to run_history) ---
    op.create_table(
        "run_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(),
            sa.ForeignKey("run_history.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("run_events")
    op.drop_table("endpoint_run_logs")
    op.drop_table("run_failures")
    op.drop_table("run_history")
    op.drop_table("field_mappings")
    op.drop_table("canvas_endpoints")
    op.drop_table("canvases")
    op.drop_table("connector_endpoints")
    op.drop_table("connectors")
    op.drop_table("qualys_config")
    op.drop_table("users")

    # Clean up enum types created by PostgreSQL
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="runstatus").drop(op.get_bind(), checkfirst=True)
