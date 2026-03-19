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

-- ============================================================
-- Seed vetting_reason_codes (controlled taxonomy)
-- ============================================================
CREATE OR REPLACE FUNCTION seed_vetting_reason_codes() RETURNS void AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'vetting_reason_codes') THEN
        INSERT INTO vetting_reason_codes (id, code, label, description, severity_default, is_active) VALUES
        (gen_random_uuid(), 'factual_error', 'Factual Error', 'The question or answer contains incorrect factual information', 'critical', true),
        (gen_random_uuid(), 'ambiguous_question', 'Ambiguous Question', 'The question text is unclear or can be interpreted multiple ways', 'major', true),
        (gen_random_uuid(), 'ambiguous_options', 'Ambiguous Options', 'Answer options are unclear, overlapping, or poorly differentiated', 'major', true),
        (gen_random_uuid(), 'wrong_answer', 'Wrong Correct Answer', 'The marked correct answer is incorrect', 'critical', true),
        (gen_random_uuid(), 'poor_distractors', 'Poor Distractors', 'MCQ distractors are implausible or too obviously wrong', 'minor', true),
        (gen_random_uuid(), 'too_easy', 'Too Easy', 'Question does not match intended difficulty (too simple)', 'minor', true),
        (gen_random_uuid(), 'too_hard', 'Too Hard', 'Question does not match intended difficulty (too complex)', 'minor', true),
        (gen_random_uuid(), 'off_topic', 'Off Topic', 'Question is not relevant to the specified subject or topic', 'major', true),
        (gen_random_uuid(), 'duplicate', 'Duplicate', 'Question is too similar to an existing question', 'major', true),
        (gen_random_uuid(), 'poor_grammar', 'Poor Grammar', 'Question has grammatical errors or poor language quality', 'minor', true),
        (gen_random_uuid(), 'incomplete', 'Incomplete', 'Question or answer is missing required information', 'major', true),
        (gen_random_uuid(), 'quality_issue', 'General Quality Issue', 'Question does not meet overall quality standards', 'major', true),
        (gen_random_uuid(), 'bloom_mismatch', 'Bloom Level Mismatch', 'Question does not match the target Bloom taxonomy level', 'minor', true),
        (gen_random_uuid(), 'formatting_issue', 'Formatting Issue', 'Question has formatting problems', 'minor', true),
        (gen_random_uuid(), 'explanation_missing', 'Explanation Missing', 'Question is missing a proper explanation', 'minor', true),
        (gen_random_uuid(), 'explanation_wrong', 'Explanation Wrong', 'Explanation does not correctly justify the answer', 'major', true),
        (gen_random_uuid(), 'references_document', 'References Document', 'Question inappropriately references the source document', 'major', true),
        (gen_random_uuid(), 'not_standalone', 'Not Standalone', 'Question cannot be answered without external context', 'major', true)
        ON CONFLICT (code) DO NOTHING;
        RAISE NOTICE 'Seeded vetting_reason_codes';
    END IF;
END;
$$ LANGUAGE plpgsql;
