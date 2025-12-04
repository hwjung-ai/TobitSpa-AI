-- Ensure documents table has tenant_id column (idempotent)
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name = 'documents' AND column_name = 'tenant_id'
  ) THEN
    EXECUTE 'ALTER TABLE documents ADD COLUMN tenant_id text';
  END IF;
END $$;
