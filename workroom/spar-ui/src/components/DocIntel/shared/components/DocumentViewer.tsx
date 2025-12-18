import { Box, Button, Divider, Typography, Switch } from '@sema4ai/components';
import { IconArrowLeft, IconArrowRight, IconMinus, IconPlus } from '@sema4ai/icons';
import { FC, useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { getFileTypeIcon, isImageFile } from '../../../../common/helpers';
import { AnnotationInputPopup } from './AnnotationInputPopup';
import { AnnotationOverlay } from './AnnotationOverlay';
import type { Annotation } from '../hooks/usePdfAnnotations';
import { usePdfDocument, useAnnotationDrawing, type PDFDocumentProxy, type PDFPageProxy } from '../hooks';

export type { PDFDocumentProxy, PDFPageProxy };

interface DocumentViewerProps {
  file: File; // PDF file to display
  parseData?: Record<string, unknown> | null; // Optional parse data for bounding boxes
  extractedData?: Record<string, unknown> | null; // Optional extracted data for citations
  isAnnotating?: boolean; // Whether annotation mode is active
  selectedFieldId?: string | null; // Controlled selected field ID for bidirectional selection
  onFieldClick?: (fieldId: string) => void; // Callback when a PDF field/annotation is clicked
  onAnnotationCreate?: (selection: {
    pageNumber: number;
    left: number;
    top: number;
    width: number;
    height: number;
    selectedText: string;
  }) => void;
  showAnnotationPopup?: boolean; // Whether to show the annotation popup
  pendingAnnotation?: Partial<Annotation> | null; // Pending annotation data
  onSaveAnnotation?: (fieldName: string, fieldValue: string) => void; // Save annotation callback
  onCancelAnnotation?: () => void; // Cancel annotation callback
}

export const DocumentViewer: FC<DocumentViewerProps> = ({
  file,
  parseData = null,
  extractedData = null,
  isAnnotating = false,
  selectedFieldId: selectedFieldIdProp,
  onFieldClick,
  onAnnotationCreate,
  showAnnotationPopup = false,
  pendingAnnotation = null,
  onSaveAnnotation,
  onCancelAnnotation,
}) => {
  // Local state for UI interactions (can be controlled via prop)
  const [selectedFieldIdInternal, setSelectedFieldIdInternal] = useState<string | null>(null);
  const selectedFieldId = selectedFieldIdProp !== undefined ? selectedFieldIdProp : selectedFieldIdInternal;

  // Use callback if provided, otherwise use internal state setter
  const handleFieldClick = useCallback(
    (fieldId: string | null) => {
      if (onFieldClick && fieldId) {
        onFieldClick(fieldId);
      } else {
        setSelectedFieldIdInternal(fieldId);
      }
    },
    [onFieldClick],
  );
  // Default to showing parse boxes if we only have parseData (no extractedData)
  const [showingParseBoxes, setShowingParseBoxes] = useState(false);

  // Track image dimensions for annotation overlay on images
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);

  // Update showingParseBoxes when parseData/extractedData changes
  useEffect(() => {
    // If we have parseData but no extractedData, show parse boxes by default
    if (parseData && !extractedData) {
      setShowingParseBoxes(true);
    } else if (extractedData && !parseData) {
      setShowingParseBoxes(false);
    }
  }, [parseData, extractedData]);

  // PDF document management hook
  const pdfState = usePdfDocument({ file });

  // Annotation drawing management hook
  const annotationState = useAnnotationDrawing({
    isAnnotating,
    pageWidth: pdfState.pageWidth,
    pageHeight: pdfState.pageHeight,
    currentPage: pdfState.currentPage,
    onAnnotationCreate,
    parseData,
    extractedData,
  });

  // Create object URL for image files (with cleanup on unmount)
  const imageUrl = useMemo(() => {
    if (isImageFile(file)) {
      return URL.createObjectURL(file);
    }
    return null;
  }, [file]);

  useEffect(() => {
    return () => {
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
      }
    };
  }, [imageUrl]);

  if (pdfState.isLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%">
        <Typography>Loading document...</Typography>
      </Box>
    );
  }

  // Non-PDF file handling
  if (!pdfState.isPdf) {
    // If it's an image, display it directly with annotation overlay support
    if (imageUrl) {
      return (
        <Box
          borderRadius="$8"
          display="flex"
          alignItems="center"
          justifyContent="center"
          height="100%"
          borderWidth="1px"
          borderColor="border.subtle"
          overflow="auto"
          padding="$16"
        >
          <Box style={{ position: 'relative', display: 'inline-block' }}>
            <img
              src={imageUrl}
              alt={file.name}
              style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }}
              onLoad={(e) => {
                const img = e.currentTarget;
                setImageDimensions({ width: img.width, height: img.height });
              }}
            />
            {/* Annotation Overlay for images - positioned over the image */}
            {imageDimensions && (parseData || extractedData) && (
              <AnnotationOverlay
                pageNumber={1}
                pageWidth={imageDimensions.width}
                pageHeight={imageDimensions.height}
                scale={1}
                parseData={parseData}
                extractedData={extractedData}
                showingParseBoxes={showingParseBoxes}
                selectedFieldId={selectedFieldId}
                setSelectedFieldId={handleFieldClick}
              />
            )}
          </Box>
        </Box>
      );
    }

    // Non-image file placeholder - show file icon and informative message
    const fileExtension = file.name.split('.').pop()?.toLowerCase() || '';
    const FileIcon = getFileTypeIcon(file.type || fileExtension);
    return (
      <Box
        borderRadius="$8"
        display="flex"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        height="100%"
        borderWidth="1px"
        borderColor="border.subtle"
        gap="$16"
        padding="$24"
      >
        <FileIcon size={100} />
        <Typography variant="body-medium" fontWeight={600}>
          {file.name}
        </Typography>
        <Typography variant="display-small" textAlign="center">
          Document preview is not available for this file type.
        </Typography>
        <Typography variant="body-medium" textAlign="center">
          Extraction results will appear in the panel on the right.
        </Typography>
      </Box>
    );
  }

  if (pdfState.error) {
    // Don't show retry button for non-PDF files
    const isNonPdfError = pdfState.error.includes('viewer only supports PDF files');

    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography color="content.error">{pdfState.error}</Typography>
        {!isNonPdfError && (
          <Button onClick={pdfState.loadPdfFromFile} variant="outline">
            Retry Loading PDF
          </Button>
        )}
      </Box>
    );
  }

  if (!pdfState.pdfBlob) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography>Loading PDF...</Typography>
        <Button onClick={pdfState.loadPdfFromFile} variant="outline">
          Retry Loading PDF
        </Button>
      </Box>
    );
  }

  return (
    <Box
      borderRadius="$8"
      display="flex"
      flexDirection="column"
      style={{ height: '100%', position: 'relative' }}
      borderWidth="1px"
      borderColor="border.subtle"
      flex="1"
      minHeight="0"
      minWidth="0"
    >
      {/* PDF Content Area */}
      <Box
        backgroundColor="background.primary"
        borderRadius="$8"
        display="flex"
        flexDirection="column"
        className="relative h-full"
        flex="1"
        minHeight="0"
      >
        <Box
          flex="1"
          style={{
            padding: '8px',
            scrollBehavior: 'smooth',
            position: 'relative',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'flex-start',
            minHeight: '0',
            overflow: 'auto',
            maxWidth: '100%',
            maxHeight: '100%',
          }}
        >
          <Box
            ref={annotationState.pageContainerRef}
            style={{
              position: 'relative',
              maxWidth: '100%',
              maxHeight: '100%',
              cursor: isAnnotating ? 'crosshair' : 'default',
            }}
            onMouseDown={annotationState.handleMouseDown}
            onMouseMove={annotationState.handleMouseMove}
            onMouseUp={annotationState.handleMouseUp}
            onMouseLeave={annotationState.handleMouseLeave}
          >
            {/* React-PDF Document and Page */}
            <Box style={{ maxWidth: '100%', maxHeight: '100%' }}>
              <Document
                file={pdfState.pdfBlob}
                onLoadSuccess={pdfState.onDocumentLoadSuccess}
                onLoadError={pdfState.onDocumentLoadError}
                loading={<Typography>Loading PDF...</Typography>}
                error={<Typography color="content.error">Failed to load PDF</Typography>}
                noData={<Typography>No PDF data</Typography>}
                className="react-pdf__Document"
              >
                <Page
                  pageNumber={pdfState.currentPage}
                  scale={pdfState.scale}
                  onLoadSuccess={pdfState.onPageLoadSuccess}
                  loading={<Typography>Loading page...</Typography>}
                  error={<Typography color="content.error">Failed to load page</Typography>}
                  noData={<Typography>No page data</Typography>}
                  className="react-pdf__Page"
                  canvasBackground="white"
                  renderTextLayer
                  renderAnnotationLayer
                />
              </Document>
            </Box>

            {/* Annotation Overlay - positioned absolutely over the PDF page */}
            {pdfState.pageWidth > 0 && pdfState.pageHeight > 0 && (
              <AnnotationOverlay
                pageNumber={pdfState.currentPage}
                pageWidth={pdfState.pageWidth}
                pageHeight={pdfState.pageHeight}
                scale={pdfState.scale}
                parseData={parseData}
                extractedData={extractedData}
                showingParseBoxes={showingParseBoxes}
                selectedFieldId={selectedFieldId}
                setSelectedFieldId={handleFieldClick}
              />
            )}

            {/* Drawing selection overlay - shown while drawing */}
            {annotationState.isDrawing && annotationState.drawStart && annotationState.drawEnd && (
              <Box
                style={{
                  position: 'absolute',
                  left: Math.min(annotationState.drawStart.x, annotationState.drawEnd.x),
                  top: Math.min(annotationState.drawStart.y, annotationState.drawEnd.y),
                  width: Math.abs(annotationState.drawEnd.x - annotationState.drawStart.x),
                  height: Math.abs(annotationState.drawEnd.y - annotationState.drawStart.y),
                  border: '2px dashed rgb(59, 130, 246)',
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  pointerEvents: 'none',
                  zIndex: 3000,
                }}
              />
            )}

            {/* Completed selection overlay - shown while popup is active */}
            {!annotationState.isDrawing && annotationState.completedSelectionBounds && showAnnotationPopup && (
              <Box
                style={{
                  position: 'absolute',
                  left: annotationState.completedSelectionBounds.left,
                  top: annotationState.completedSelectionBounds.top,
                  width: annotationState.completedSelectionBounds.width,
                  height: annotationState.completedSelectionBounds.height,
                  border: '2px dashed rgb(59, 130, 246)',
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  pointerEvents: 'none',
                  zIndex: 3000,
                }}
              />
            )}
          </Box>
        </Box>

        {/* Page Number Display - Fixed at bottom of PDF viewer */}
        <Box
          textAlign="center"
          fontSize="$12"
          color="content.subtle"
          backgroundColor="background.primary"
          borderRadius="$4"
          boxShadow="0 1px 2px 0 rgba(0, 0, 0, 0.05)"
          style={{
            position: 'absolute',
            bottom: '4rem',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: '10',
            padding: '3px 16px',
          }}
        >
          Page {pdfState.currentPage} of {pdfState.numPages}
        </Box>
      </Box>

      {/* Bottom Controls */}
      <Box
        padding="$8"
        backgroundColor="background.primary"
        flexShrink="0"
        display="flex"
        alignItems="center"
        justifyContent="center"
      >
        <Box display="flex" alignItems="center" justifyContent="space-between" gap="$16">
          {/* Page Navigation */}
          <Box display="flex" alignItems="center">
            <Button
              disabled={pdfState.currentPage <= 1}
              variant="ghost"
              round
              onClick={() => pdfState.goToPage(pdfState.currentPage - 1)}
            >
              <IconArrowLeft />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '80px' }}>
              {pdfState.currentPage} / {pdfState.numPages}
            </Typography>
            <Button
              disabled={pdfState.currentPage >= pdfState.numPages}
              variant="ghost"
              round
              onClick={() => pdfState.goToPage(pdfState.currentPage + 1)}
            >
              <IconArrowRight />
            </Button>
          </Box>

          <Divider orientation="vertical" />

          {/* Parse/Extract Toggle - only show when both parse and extract data exist */}
          {parseData && extractedData && (
            <>
              <Box display="flex" alignItems="center" gap="$8" style={{ transition: 'opacity 0.3s ease-in-out' }}>
                <Typography fontSize="$14">1st Pass</Typography>
                <Switch
                  checked={!showingParseBoxes}
                  onChange={(e) => setShowingParseBoxes(!e.target.checked)}
                  aria-labelledby="parse-extract-toggle"
                />
                <Typography fontSize="$14">Detailed</Typography>
              </Box>
              <Divider orientation="vertical" />
            </>
          )}

          {/* Scale Controls */}
          <Box display="flex" alignItems="center">
            <Button
              disabled={pdfState.scale <= 0.5}
              variant="ghost"
              round
              onClick={() => pdfState.changeScale(pdfState.scale - 0.25)}
            >
              <IconMinus />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '70px' }}>
              {pdfState.zoomPercentage}%
            </Typography>
            <Button
              disabled={pdfState.scale >= 3}
              variant="ghost"
              round
              onClick={() => pdfState.changeScale(pdfState.scale + 0.25)}
            >
              <IconPlus />
            </Button>
          </Box>

          {/* Annotate Button - Temporarily hidden */}
          {/* {onAnnotateToggle && (
            <Button
              variant={isAnnotating ? 'primary' : 'outline'}
              onClick={onAnnotateToggle}
              round
              icon={IconPencil}
            >
              {isAnnotating ? 'Exit Annotate' : 'Annotate'}
            </Button>
          )} */}
        </Box>
      </Box>

      {/* Annotation Input Popup - rendered via portal for proper overlay positioning */}
      {showAnnotationPopup &&
        pendingAnnotation &&
        annotationState.annotationPopupPosition &&
        createPortal(
          <AnnotationInputPopup
            annotation={pendingAnnotation}
            onSave={(fieldName, fieldValue) => {
              onSaveAnnotation?.(fieldName, fieldValue);
              annotationState.setAnnotationPopupPosition(null);
              annotationState.setCompletedSelectionBounds(null);
            }}
            onCancel={() => {
              onCancelAnnotation?.();
              annotationState.setAnnotationPopupPosition(null);
              annotationState.setCompletedSelectionBounds(null);
            }}
            position={annotationState.annotationPopupPosition}
          />,
          document.body,
        )}
    </Box>
  );
};
