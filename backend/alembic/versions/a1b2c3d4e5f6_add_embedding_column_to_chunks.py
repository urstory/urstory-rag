"""add embedding column to chunks

Revision ID: a1b2c3d4e5f6
Revises: cac992dd33a5
Create Date: 2026-03-01
"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "cac992dd33a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(1024)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.drop_column("chunks", "embedding")
