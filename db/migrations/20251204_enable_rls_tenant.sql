-- Enable Row-Level Security and basic tenant isolation policies

-- Enable RLS on documents and doc_chunks to support multi-tenant isolation
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE doc_chunks ENABLE ROW LEVEL SECURITY;

-- Create tenant isolation policy for documents
CREATE POLICY IF NOT EXISTS tenant_isolation_documents ON documents
FOR ALL USING (tenant_id IS NULL OR tenant_id = current_setting('tobitspa.tenant_id', true));

-- Create tenant isolation policy for doc_chunks
CREATE POLICY IF NOT EXISTS tenant_isolation_doc_chunks ON doc_chunks
FOR ALL USING (tenant_id IS NULL OR tenant_id = current_setting('tobitspa.tenant_id', true));
