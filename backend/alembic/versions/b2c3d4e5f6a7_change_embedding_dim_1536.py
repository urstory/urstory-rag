"""Change embedding column from vector(1024) to vector(1536) for OpenAI.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-01
"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 인덱스 삭제
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    # 기존 임베딩 데이터 모두 삭제 (차원 변경으로 호환 불가)
    op.execute("UPDATE chunks SET embedding = NULL")
    # 컬럼 타입 변경: vector(1024) → vector(1536)
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1536)")
    # 새 HNSW 인덱스 생성
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("UPDATE chunks SET embedding = NULL")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1024)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200)"
    )
