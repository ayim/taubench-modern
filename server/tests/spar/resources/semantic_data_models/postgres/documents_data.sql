-- Test data for documents table with JSON/JSONB nested structures
-- Data includes various invoice documents for testing JSON queries
INSERT INTO
  invoice_documents (
    document_id,
    document_title,
    document_layout,
    model_type,
    content_extracted,
    content_translated,
    created_at,
    updated_at
  )
VALUES
  -- Document 1: Koch Energy Services invoice with matching totals
  (
    'doc-001',
    'Koch Invoice March 2025.pdf',
    'standard',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery", "amount": 100000, "volume": 10000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}], "invoice_total": 150000, "invoice_number": "INV-001", "invoice_date": "2025-03-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery", "amount": 100000, "volume": 10000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}], "Invoice_details": {"invoice_total": 150000, "invoice_number": "INV-001", "invoice_date": "2025-03-01"}}',
    '2025-03-01 10:00:00+00',
    '2025-03-01 10:00:00+00'
  ),
  -- Document 2: Koch Energy Services invoice with mismatched totals
  (
    'doc-002',
    'Koch Invoice April 2025.pdf',
    'standard',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery", "amount": 200000, "volume": 20000, "price": 10.0}, {"description": "Transport fee", "amount": 75000, "volume": 7500, "price": 10.0}], "invoice_total": 280000, "invoice_number": "INV-002", "invoice_date": "2025-04-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery", "amount": 200000, "volume": 20000, "price": 10.0}, {"description": "Transport fee", "amount": 75000, "volume": 7500, "price": 10.0}], "Invoice_details": {"invoice_total": 275000, "invoice_number": "INV-002", "invoice_date": "2025-04-01"}}',
    '2025-04-01 10:00:00+00',
    '2025-04-01 10:00:00+00'
  ),
  -- Document 3: Different customer with matching totals
  (
    'doc-003',
    'Acme Invoice March 2025.pdf',
    'standard',
    'standard_invoices',
    '{"customer": {"name": "Acme Corporation", "email": "acme@example.com", "address": "456 Oak Ave"}, "line_items": [{"description": "Product A", "amount": 30000, "quantity": 100, "price": 300.0}, {"description": "Product B", "amount": 20000, "quantity": 50, "price": 400.0}], "invoice_total": 50000, "invoice_number": "INV-003", "invoice_date": "2025-03-15"}',
    '{"Buyer": {"name": "Acme Corporation", "email": "acme@example.com", "address": "456 Oak Ave"}, "Transactions": [{"description": "Product A", "amount": 30000, "quantity": 100, "price": 300.0}, {"description": "Product B", "amount": 20000, "quantity": 50, "price": 400.0}], "Invoice_details": {"invoice_total": 50000, "invoice_number": "INV-003", "invoice_date": "2025-03-15"}}',
    '2025-03-15 10:00:00+00',
    '2025-03-15 10:00:00+00'
  ),
  -- Document 4: Koch Energy Services with single line item
  (
    'doc-004',
    'Koch Invoice May 2025.pdf',
    'standard',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery", "amount": 500000, "volume": 50000, "price": 10.0}], "invoice_total": 500000, "invoice_number": "INV-004", "invoice_date": "2025-05-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery", "amount": 500000, "volume": 50000, "price": 10.0}], "Invoice_details": {"invoice_total": 500000, "invoice_number": "INV-004", "invoice_date": "2025-05-01"}}',
    '2025-05-01 10:00:00+00',
    '2025-05-01 10:00:00+00'
  ),
  -- Document 5: Different customer with mismatched totals
  (
    'doc-005',
    'Beta Corp Invoice April 2025.pdf',
    'standard',
    'standard_invoices',
    '{"customer": {"name": "Beta Corp", "email": "beta@example.com", "address": "789 Pine St"}, "line_items": [{"description": "Service A", "amount": 10000, "hours": 100, "rate": 100.0}, {"description": "Service B", "amount": 15000, "hours": 150, "rate": 100.0}, {"description": "Service C", "amount": 8000, "hours": 80, "rate": 100.0}], "invoice_total": 35000, "invoice_number": "INV-005", "invoice_date": "2025-04-15"}',
    '{"Buyer": {"name": "Beta Corp", "email": "beta@example.com", "address": "789 Pine St"}, "Transactions": [{"description": "Service A", "amount": 10000, "hours": 100, "rate": 100.0}, {"description": "Service B", "amount": 15000, "hours": 150, "rate": 100.0}, {"description": "Service C", "amount": 8000, "hours": 80, "rate": 100.0}], "Invoice_details": {"invoice_total": 33000, "invoice_number": "INV-005", "invoice_date": "2025-04-15"}}',
    '2025-04-15 10:00:00+00',
    '2025-04-15 10:00:00+00'
  ),
  -- Document 6: Koch Energy Services with multiple line items and mismatch
  (
    'doc-006',
    'Koch Invoice June 2025.pdf',
    'detailed',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery Zone A", "amount": 120000, "volume": 12000, "price": 10.0}, {"description": "Gas delivery Zone B", "amount": 180000, "volume": 18000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}, {"description": "Storage fee", "amount": 30000, "volume": 3000, "price": 10.0}], "invoice_total": 380000, "invoice_number": "INV-006", "invoice_date": "2025-06-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery Zone A", "amount": 120000, "volume": 12000, "price": 10.0}, {"description": "Gas delivery Zone B", "amount": 180000, "volume": 18000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}, {"description": "Storage fee", "amount": 30000, "volume": 3000, "price": 10.0}], "Invoice_details": {"invoice_total": 385000, "invoice_number": "INV-006", "invoice_date": "2025-06-01"}}',
    '2025-06-01 10:00:00+00',
    '2025-06-01 10:00:00+00'
  ),
  -- Document 7: Gamma Inc with empty line items
  (
    'doc-007',
    'Gamma Inc Invoice May 2025.pdf',
    'simple',
    'standard_invoices',
    '{"customer": {"name": "Gamma Inc", "email": "gamma@example.com", "address": "321 Elm St"}, "line_items": [], "invoice_total": 0, "invoice_number": "INV-007", "invoice_date": "2025-05-15"}',
    '{"Buyer": {"name": "Gamma Inc", "email": "gamma@example.com", "address": "321 Elm St"}, "Transactions": [], "Invoice_details": {"invoice_total": 0, "invoice_number": "INV-007", "invoice_date": "2025-05-15"}}',
    '2025-05-15 10:00:00+00',
    '2025-05-15 10:00:00+00'
  ),
  -- Document 8: Koch Energy Services with NULL invoice_total in translated_content
  (
    'doc-008',
    'Koch Invoice July 2025.pdf',
    'standard',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery", "amount": 250000, "volume": 25000, "price": 10.0}], "invoice_total": 250000, "invoice_number": "INV-008", "invoice_date": "2025-07-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery", "amount": 250000, "volume": 25000, "price": 10.0}], "Invoice_details": {"invoice_total": null, "invoice_number": "INV-008", "invoice_date": "2025-07-01"}}',
    '2025-07-01 10:00:00+00',
    '2025-07-01 10:00:00+00'
  );