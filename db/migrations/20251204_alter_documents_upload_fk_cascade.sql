-- Migration: alter documents_upload_id_fkey to cascade delete
DO $$ BEGIN
  -- Ensure uploads table exists
  IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'uploads') THEN
    EXECUTE '
    CREATE TABLE public.uploads (
      id bigserial NOT NULL,
      title text NOT NULL,
      owner text NULL,
      tenant_id text NULL,
      total_files int NULL,
      status text NULL,
      created_at timestamptz DEFAULT now() NULL,
      CONSTRAINT uploads_pkey PRIMARY KEY (id)
    )';
  END IF;

  -- Ensure documents.upload_id column exists
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='documents' AND column_name='upload_id') THEN
    EXECUTE 'ALTER TABLE documents ADD COLUMN upload_id BIGINT';
  END IF;

  -- Drop existing FK if present
  IF EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
    WHERE tc.table_name = 'documents'
      AND tc.constraint_type = 'FOREIGN KEY'
      AND ccu.column_name = 'upload_id'
      AND tc.constraint_name = 'documents_upload_id_fkey'
  ) THEN
    EXECUTE 'ALTER TABLE documents DROP CONSTRAINT documents_upload_id_fkey';
  END IF;

  -- Add/update FK with cascade if not exists
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.table_constraints tc
    JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
    WHERE tc.table_name = 'documents'
      AND tc.constraint_type = 'FOREIGN KEY'
      AND ccu.column_name = 'upload_id'
      AND tc.constraint_name = 'documents_upload_id_fkey'
  ) THEN
    EXECUTE 'ALTER TABLE documents ADD CONSTRAINT documents_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE';
  END IF;
END $$;
