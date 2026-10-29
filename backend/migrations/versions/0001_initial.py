"""Initial comparison records with immutable OCR snapshots and revision audit."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None


def upgrade():
    op.create_table("comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("reviewed", sa.Boolean, nullable=False),
        sa.Column("edited", sa.Boolean, nullable=False),
        sa.Column("result", sa.JSON, nullable=False))
    op.create_index("ix_comparisons_created_at", "comparisons", ["created_at"])
    op.create_table("documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("comparison_id", sa.String(36), sa.ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("ocr_text", sa.Text, nullable=False),
        sa.Column("evidence", sa.JSON, nullable=False),
        sa.Column("original", sa.JSON, nullable=False),
        sa.Column("current", sa.JSON, nullable=False))
    op.create_index("ix_documents_comparison_id", "documents", ["comparison_id"])
    op.create_table("comparison_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("comparison_id", sa.String(36), sa.ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("values", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False))
    op.create_index("ix_comparison_revisions_comparison_id", "comparison_revisions", ["comparison_id"])


def downgrade():
    op.drop_table("comparison_revisions")
    op.drop_table("documents")
    op.drop_table("comparisons")
