import { ServerResponse } from '../../../queries/shared';

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
