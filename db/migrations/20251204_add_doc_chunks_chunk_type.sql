-- Migration: add chunk_type to doc_chunks (page/paragraph/sentence granularity)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'doc_chunks' AND column_name = 'chunk_type') THEN
    EXECUTE 'ALTER TABLE doc_chunks ADD COLUMN chunk_type VARCHAR(20) DEFAULT ''page''';
  END IF;
  -- Backfill existing rows and enforce NOT NULL
  EXECUTE 'UPDATE doc_chunks SET chunk_type = COALESCE(chunk_type, ''page'')';
  EXECUTE 'ALTER TABLE doc_chunks ALTER COLUMN chunk_type SET NOT NULL';
END $$;
