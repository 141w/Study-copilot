"""add pgvector extension and document_chunks table

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-08-30

Replaces file-based FAISS + BM25 vector storage with PostgreSQL + pgvector.
Adds the pgvector extension and a new document_chunks table for embedding storage,
keyword search (GIN tsvector index), and HNSW vector indexing.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable pgvector extension and create document_chunks table with indexes."""
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create document_chunks table (use raw SQL for pgvector VECTOR type)
    op.execute("""
        CREATE TABLE document_chunks (
            id VARCHAR NOT NULL,
            document_id VARCHAR NOT NULL,
            content TEXT NOT NULL,
            embedding vector(768),
            chunk_index INTEGER DEFAULT 0 NOT NULL,
            chunk_metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
        )
    """)

    # HNSW index for cosine similarity vector search
    op.execute("""
        CREATE INDEX ix_document_chunks_doc_embedding
        ON document_chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # GIN index for full-text keyword search (replaces BM25)
    # Create a simple zh text search configuration for CJK (no stop words + simple segmentation)
    op.execute("""
        CREATE TEXT SEARCH CONFIGURATION zh (COPY = simple)
    """)
    op.execute("""
        CREATE INDEX ix_document_chunks_content_fts
        ON document_chunks
        USING gin (to_tsvector('zh', content))
    """)

    # Composite index for common query: WHERE document_id = ? ORDER BY created_at
    op.create_index(
        "ix_document_chunks_doc_created",
        "document_chunks",
        ["document_id", "created_at"],
    )

    # Index on metadata for JSONB queries
    op.create_index(
        "ix_document_chunks_metadata",
        "document_chunks",
        ["chunk_metadata"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Drop document_chunks table and extension."""
    op.drop_index("ix_document_chunks_metadata", table_name="document_chunks")
    op.drop_index("ix_document_chunks_doc_created", table_name="document_chunks")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_fts")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_doc_embedding")
    op.drop_table("document_chunks")
    op.execute("DROP EXTENSION IF EXISTS vector")


import sqlalchemy as sa  # noqa: E402 — needed by Alembic op calls above
