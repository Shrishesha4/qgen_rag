-- Backfill subjects.total_questions from actual question counts
UPDATE subjects s SET total_questions = (
  SELECT count(*) FROM questions q
  WHERE q.subject_id = s.id AND q.is_archived = false AND q.is_latest = true
);

-- Backfill topics.total_questions from actual question counts  
UPDATE topics t SET total_questions = (
  SELECT count(*) FROM questions q
  WHERE q.topic_id = t.id AND q.is_archived = false AND q.is_latest = true
);

-- Randomize bloom_taxonomy_level for existing 'apply' questions
UPDATE questions SET bloom_taxonomy_level = (
  CASE (random() * 5)::int
    WHEN 0 THEN 'remember'
    WHEN 1 THEN 'understand'
    WHEN 2 THEN 'apply'
    WHEN 3 THEN 'analyze'
    WHEN 4 THEN 'evaluate'
    ELSE 'create'
  END
) WHERE bloom_taxonomy_level = 'apply';

-- Backfill remaining NULL document_id on questions
UPDATE questions q SET document_id = (
  SELECT d.id FROM documents d
  WHERE d.subject_id = q.subject_id AND d.processing_status = 'completed'
  ORDER BY d.upload_timestamp DESC LIMIT 1
) WHERE q.document_id IS NULL AND q.subject_id IS NOT NULL;

-- Backfill vetting_logs reason_codes from feedback text
UPDATE vetting_logs SET reason_codes = ARRAY['poor_grammar']
  WHERE reason_codes IS NULL AND (feedback ILIKE '%rephrase%' OR feedback ILIKE '%re-phrase%' OR feedback ILIKE '%reword%');
UPDATE vetting_logs SET reason_codes = ARRAY['quality_issue']
  WHERE reason_codes IS NULL AND decision IN ('reject', 'edit');

-- Generate share_token for documents that don't have one
UPDATE documents SET share_token = encode(gen_random_bytes(16), 'hex')
  WHERE share_token IS NULL;
