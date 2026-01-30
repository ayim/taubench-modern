import type { components, ServerResponse } from '@sema4ai/agent-server-interface';

/**
 * Shared types for Document Intelligence components
 */

/**
 * Parse result type from the document-intelligence/documents/parse endpoint
 * Represents the chunks array from the parse response
 */
export type ParseResult = ServerResponse<'post', '/api/v2/document-intelligence/documents/parse'>['result']['chunks'];

/**
 * Full parse response from the document-intelligence/documents/parse endpoint
 */
export type ParseResponse = ServerResponse<'post', '/api/v2/document-intelligence/documents/parse'>;

/**
 * Extract schema generation response
 */
export type ExtractSchemaResponse = ServerResponse<'post', '/api/v2/document-intelligence/documents/generate-schema'>;

/**
 * Extract result type from the document-intelligence/documents/extract endpoint
 */
export type ExtractResponse = ServerResponse<'post', '/api/v2/document-intelligence/documents/extract'>;

/**
 * Extraction schema type from agent-server-interface
 * Used for structuring extraction schemas in document layouts
 */
export type ExtractionSchemaPayload = components['schemas']['_ExtractionSchema'];
