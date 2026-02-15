-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create initial schema (tables will be created by SQLAlchemy)
-- This file is for any additional setup needed

-- ============================================================
-- Vector Indexes for Semantic Search Performance
-- ============================================================
-- These indexes significantly improve vector similarity search.
-- IVFFlat is faster to build and good for most use cases.
-- HNSW is slower to build but faster for queries (use for production at scale).

-- Function to create vector indexes after tables exist
-- This is idempotent and safe to run multiple times
CREATE OR REPLACE FUNCTION create_vector_indexes() RETURNS void AS $$
BEGIN
    -- IVFFlat index for document chunk embeddings
    -- lists = 100 is good for up to ~100k vectors
    -- For larger datasets, use: lists = sqrt(num_vectors)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'document_chunks') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunk_embedding_ivfflat') THEN
            -- Need at least 100 rows for IVFFlat with lists=100
            IF (SELECT COUNT(*) FROM document_chunks) >= 100 THEN
                CREATE INDEX idx_chunk_embedding_ivfflat 
                ON document_chunks 
                USING ivfflat (chunk_embedding vector_cosine_ops) 
                WITH (lists = 100);
                RAISE NOTICE 'Created IVFFlat index on document_chunks.chunk_embedding';
            ELSE
                RAISE NOTICE 'Skipping IVFFlat index: need at least 100 rows (have %)', (SELECT COUNT(*) FROM document_chunks);
            END IF;
        END IF;
    END IF;

    -- IVFFlat index for question embeddings (for deduplication)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'questions') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_question_embedding_ivfflat') THEN
            IF (SELECT COUNT(*) FROM questions WHERE question_embedding IS NOT NULL) >= 100 THEN
                CREATE INDEX idx_question_embedding_ivfflat 
                ON questions 
                USING ivfflat (question_embedding vector_cosine_ops) 
                WITH (lists = 100);
                RAISE NOTICE 'Created IVFFlat index on questions.question_embedding';
            ELSE
                RAISE NOTICE 'Skipping IVFFlat index on questions: need at least 100 rows';
            END IF;
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- Regular B-tree Indexes for Common Queries
-- ============================================================

-- Function to create regular indexes
CREATE OR REPLACE FUNCTION create_btree_indexes() RETURNS void AS $$
BEGIN
    -- Document chunks: lookup by document
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'document_chunks') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_document_id') THEN
            CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_chunks_document_index') THEN
            CREATE INDEX idx_chunks_document_index ON document_chunks(document_id, chunk_index);
        END IF;
    END IF;

    -- Questions: common query patterns
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'questions') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_questions_document_id') THEN
            CREATE INDEX idx_questions_document_id ON questions(document_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_questions_subject_id') THEN
            CREATE INDEX idx_questions_subject_id ON questions(subject_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_questions_vetting_status') THEN
            CREATE INDEX idx_questions_vetting_status ON questions(vetting_status) WHERE is_archived = false;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_questions_generated_at') THEN
            CREATE INDEX idx_questions_generated_at ON questions(generated_at DESC);
        END IF;
    END IF;

    -- Documents: user lookup
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'documents') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_user_id') THEN
            CREATE INDEX idx_documents_user_id ON documents(user_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_user_status') THEN
            CREATE INDEX idx_documents_user_status ON documents(user_id, processing_status);
        END IF;
    END IF;

    -- Generation sessions
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'generation_sessions') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_sessions_user_id') THEN
            CREATE INDEX idx_sessions_user_id ON generation_sessions(user_id);
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_sessions_document_id') THEN
            CREATE INDEX idx_sessions_document_id ON generation_sessions(document_id);
        END IF;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Note: These functions should be called after SQLAlchemy creates tables
-- Either via: SELECT create_btree_indexes(); SELECT create_vector_indexes();
-- Or automatically in the application startup

-- Grant permissions if needed for specific roles
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qgen_user;
