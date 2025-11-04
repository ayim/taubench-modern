-- Invoice documents table schema for testing JSON/JSONB queries
-- This table contains invoice documents with nested JSON structures
CREATE TABLE IF NOT EXISTS invoice_documents (
  document_id TEXT PRIMARY KEY,
  document_title TEXT,
  document_layout TEXT,
  model_type TEXT NOT NULL,
  content_extracted JSONB,
  content_translated JSON,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Create indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_invoice_documents_model_type ON invoice_documents(model_type);
CREATE INDEX IF NOT EXISTS idx_invoice_documents_created_at ON invoice_documents(created_at);
CREATE INDEX IF NOT EXISTS idx_invoice_documents_updated_at ON invoice_documents(updated_at);
-- JSONB GIN index for content_extracted queries
CREATE INDEX IF NOT EXISTS idx_invoice_documents_content_extracted ON invoice_documents USING GIN (content_extracted);
-- Comments for documentation
COMMENT ON TABLE invoice_documents IS 'Invoice documents with JSON/JSONB content for testing nested data queries';
COMMENT ON COLUMN invoice_documents.document_id IS 'Unique identifier for the document';
COMMENT ON COLUMN invoice_documents.document_title IS 'Name of the document file';
COMMENT ON COLUMN invoice_documents.document_layout IS 'Layout template used for the document';
COMMENT ON COLUMN invoice_documents.model_type IS 'Data model type (e.g., koch_invoices)';
COMMENT ON COLUMN invoice_documents.content_extracted IS 'JSONB column with structured invoice data including customer info and line items';
COMMENT ON COLUMN invoice_documents.content_translated IS 'JSON column with transformed invoice data including buyer info and transactions';
COMMENT ON COLUMN invoice_documents.created_at IS 'Timestamp when the document was created';
COMMENT ON COLUMN invoice_documents.updated_at IS 'Timestamp when the document was last updated';