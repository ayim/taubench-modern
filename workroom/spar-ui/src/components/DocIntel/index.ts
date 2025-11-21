/**
 * DocIntel - Modular Document Intelligence System
 *
 * A refactored, modular architecture for document intelligence features.
 * Each feature (ParseOnly, ExtractOnly, CreateDataModel) is independent and
 * self-contained, with shared utilities and components in the shared/ folder.
 */

// Shared utilities and components
export * from './shared/constants/interfaceLabels';
export * from './shared/hooks/useAgentDocIntelCapabilities';
export { DocumentViewer } from './shared/components/DocumentViewer';
export type { PDFDocumentProxy, PDFPageProxy } from './shared/components/DocumentViewer';

// Feature modules
export * from './ParseOnly';
export * from './ExtractOnly';
// CreateDataModel is a placeholder for now
