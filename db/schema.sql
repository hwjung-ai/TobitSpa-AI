-- SQL script to define a flexible and extensible database schema for the AIOps project.
-- This schema can accommodate various asset types, including IT, power, and buildings.
-- This script is for PostgreSQL.

-- Drop existing tables to ensure a clean setup
DROP TABLE IF EXISTS chat_history, work_history, events, metrics, doc_chunks, documents, assets;

-- Table for storing uploaded manual documents.
CREATE TABLE documents (
	id bigserial NOT NULL,
	title text NOT NULL,
	category text NULL,
	"system" text NULL,
	"owner" text NULL,
	tags _text NULL,
	source_type text NULL,
	original_path text NULL,
	converted_pdf text NULL,
	created_at timestamptz DEFAULT now() NULL,
	CONSTRAINT documents_pkey PRIMARY KEY (id)
);

-- Table for storing indexed chunks of text from documents for vector search.
CREATE TABLE doc_chunks (
	id bigserial NOT NULL,
	document_id int8 NULL,
	chunk_index int4 NULL,
	"content" text NULL,
	page_num int4 NULL,
	source_path text NULL,
	highlight_anchor text NULL,
	embedding public.vector NULL,
	created_at timestamptz DEFAULT now() NULL,
	CONSTRAINT doc_chunks_pkey PRIMARY KEY (id),
	CONSTRAINT doc_chunks_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id) ON DELETE CASCADE
);
CREATE INDEX doc_chunks_doc_id_idx ON public.doc_chunks USING btree (document_id);


-- Generic table for all configuration items/assets (e.g., IT devices, buildings, power units).
-- The 'asset_type' column is used to categorize items, and the 'attributes' JSONB column
-- provides flexibility to store different information for different asset types.
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    asset_type VARCHAR(100) NOT NULL, -- e.g., 'IT_DEVICE', 'BUILDING', 'POWER_TRANSFORMER'
    name VARCHAR(255) NOT NULL,
    attributes JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table for storing maintenance and work history for any asset.
CREATE TABLE work_history (
    history_id SERIAL PRIMARY KEY,
    asset_id INTEGER REFERENCES assets(id),
    work_date TIMESTAMPTZ DEFAULT NOW(),
    worker_name VARCHAR(255),
    work_type VARCHAR(100), -- e.g., 'maintenance', 'repair', 'update', 'install'
    description TEXT NOT NULL
);

-- Table for storing system events and logs from any asset.
-- This table is intended to be converted into a TimescaleDB hypertable
-- for efficient time-series data handling.
CREATE TABLE events (
    event_time TIMESTAMPTZ NOT NULL,
    asset_id INTEGER,
    severity VARCHAR(50), -- e.g., 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    event_type VARCHAR(100),
    description TEXT,
    CONSTRAINT fk_asset FOREIGN KEY(asset_id) REFERENCES assets(id)
);
-- After creating the table, run this in psql to enable TimescaleDB:
-- SELECT create_hypertable('events', 'event_time');


-- Table for storing time-series metrics from any asset.
-- This is designed for use with TimescaleDB.
CREATE TABLE metrics (
    ts TIMESTAMPTZ NOT NULL,
    asset_id INTEGER REFERENCES assets(id),
    metric VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION NOT NULL
);
-- After creating the table, convert it to a hypertable:
-- SELECT create_hypertable('metrics', 'ts');


-- Table for storing chat history for conversation retrieval.
CREATE TABLE chat_history (
    message_id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    "timestamp" TIMESTAMPTZ DEFAULT NOW(),
    role VARCHAR(50) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    metadata JSONB -- For storing charts, tables, etc.
);

-- Add comments to explain the schema
COMMENT ON TABLE documents IS 'Stores metadata for uploaded manual documents.';
COMMENT ON TABLE doc_chunks IS 'Stores searchable, embedded chunks of text extracted from the documents.';
COMMENT ON TABLE assets IS 'Stores core configuration data for all assets (IT, building, power, etc.). The JSONB attributes column allows for flexible, extensible schemas for each asset type.';
COMMENT ON TABLE work_history IS 'Logs all maintenance, repair, and update activities performed on any asset.';
COMMENT ON TABLE events IS 'Captures time-series event and log data from any asset. Intended for use as a TimescaleDB hypertable.';
COMMENT ON TABLE metrics IS 'Captures time-series numerical metric data from any asset (e.g., CPU usage, temperature). Intended for use as a TimescaleDB hypertable.';
COMMENT ON TABLE chat_history IS 'Records all user and assistant interactions for session history and retrieval.';

-- Optional: Create a GIN index on the attributes column for faster JSONB searches.
CREATE INDEX idx_assets_attributes ON assets USING GIN (attributes);
