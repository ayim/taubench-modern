import { Box, Button, Divider, Typography, Switch } from '@sema4ai/components';
import { IconArrowLeft, IconArrowRight, IconMinus, IconPlus } from '@sema4ai/icons';
import { FC, useState, useEffect, useCallback } from 'react';
import { pdfjs, Document, Page } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

import { AnnotationOverlay } from './AnnotationOverlay';

export type PDFDocumentProxy = pdfjs.PDFDocumentProxy;
export type PDFPageProxy = pdfjs.PDFPageProxy;

interface DocumentViewerProps {
  file: File; // PDF file to display
  parseData?: Record<string, unknown> | null; // Optional parse data for bounding boxes
  extractedData?: Record<string, unknown> | null; // Optional extracted data for citations
}

export const DocumentViewer: FC<DocumentViewerProps> = ({ file, parseData = null, extractedData = null }) => {
  // Local state for UI interactions
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  // Default to showing parse boxes if we only have parseData (no extractedData)
  const [showingParseBoxes, setShowingParseBoxes] = useState(false);

  // Update showingParseBoxes when parseData/extractedData changes
  useEffect(() => {
    // If we have parseData but no extractedData, show parse boxes by default
    if (parseData && !extractedData) {
      setShowingParseBoxes(true);
    } else if (extractedData && !parseData) {
      setShowingParseBoxes(false);
    }
  }, [parseData, extractedData]);

  const [currentPage, setCurrentPage] = useState<number>(1);
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState<number>(1.5); // Default 150% zoom
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);

  // PDF dimensions for overlay positioning
  const [pageWidth, setPageWidth] = useState<number>(0);
  const [pageHeight, setPageHeight] = useState<number>(0);

  const zoomPercentage = Math.round(scale * 100);

  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

  const loadPdfFromFile = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      if (!isPdf) {
        setError(
          'This viewer only supports PDF files. Your document has been processed, but annotations cannot be displayed.',
        );
        setIsLoading(false);
        return;
      }

      // Create a blob from the File object
      const blob = new Blob([file], { type: 'application/pdf' });
      setPdfBlob(blob);

      // For now, assume 1 page - in real implementation this comes from PDF parsing
      setNumPages(1);
      setCurrentPage(1);
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load PDF';
      setError(errorMsg);
    } finally {
      setIsLoading(false);
    }
  }, [file, isPdf]);

  // Load PDF when component mounts or file changes
  useEffect(() => {
    loadPdfFromFile();
  }, [loadPdfFromFile]);

  // PDF document loading handlers
  const onDocumentLoadSuccess = (document: PDFDocumentProxy) => {
    setNumPages(document.numPages);
    setCurrentPage(1);
  };

  const onDocumentLoadError = (err: Error) => {
    setError(`Failed to load PDF: ${err.message}`);
  };

  // Page rendering handlers
  const onPageLoadSuccess = (page: PDFPageProxy) => {
    const viewport = page.getViewport({ scale: 1 });
    setPageWidth(viewport.width * scale);
    setPageHeight(viewport.height * scale);
  };

  // Navigation handlers
  const goToPage = (pageNumber: number) => {
    if (pageNumber >= 1 && pageNumber <= numPages) {
      setCurrentPage(pageNumber);
    }
  };

  const changeScale = (newScale: number) => {
    const clampedScale = Math.max(0.5, Math.min(3.0, newScale));
    setScale(clampedScale);
  };

  if (isLoading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%">
        <Typography>Loading PDF...</Typography>
      </Box>
    );
  }

  if (error) {
    // Don't show retry button for non-PDF files
    const isNonPdfError = error.includes('viewer only supports PDF files');

    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography color="content.error">{error}</Typography>
        {!isNonPdfError && (
          <Button onClick={loadPdfFromFile} variant="outline">
            Retry Loading PDF
          </Button>
        )}
      </Box>
    );
  }

  if (!pdfBlob) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" flexDirection="column" gap="$16">
        <Typography>Loading PDF...</Typography>
        <Button onClick={loadPdfFromFile} variant="outline">
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
          <Box style={{ position: 'relative', maxWidth: '100%', maxHeight: '100%' }}>
            {/* React-PDF Document and Page */}
            <Box style={{ maxWidth: '100%', maxHeight: '100%' }}>
              <Document
                file={pdfBlob}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={onDocumentLoadError}
                loading={<Typography>Loading PDF...</Typography>}
                error={<Typography color="content.error">Failed to load PDF</Typography>}
                noData={<Typography>No PDF data</Typography>}
                className="react-pdf__Document"
              >
                <Page
                  pageNumber={currentPage}
                  scale={scale}
                  onLoadSuccess={onPageLoadSuccess}
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
            {pageWidth > 0 && pageHeight > 0 && (
              <AnnotationOverlay
                pageNumber={currentPage}
                pageWidth={pageWidth}
                pageHeight={pageHeight}
                scale={scale}
                parseData={parseData}
                extractedData={extractedData}
                showingParseBoxes={showingParseBoxes}
                selectedFieldId={selectedFieldId}
                onFieldSelect={setSelectedFieldId}
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
          Page {currentPage} of {numPages}
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
            <Button disabled={currentPage <= 1} variant="ghost" round onClick={() => goToPage(currentPage - 1)}>
              <IconArrowLeft />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '80px' }}>
              {currentPage} / {numPages}
            </Typography>
            <Button disabled={currentPage >= numPages} variant="ghost" round onClick={() => goToPage(currentPage + 1)}>
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
            <Button disabled={scale <= 0.5} variant="ghost" round onClick={() => changeScale(scale - 0.25)}>
              <IconMinus />
            </Button>
            <Typography fontSize="$16" fontWeight="medium" textAlign="center" style={{ minWidth: '70px' }}>
              {zoomPercentage}%
            </Typography>
            <Button disabled={scale >= 3.0} variant="ghost" round onClick={() => changeScale(scale + 0.25)}>
              <IconPlus />
            </Button>
          </Box>
        </Box>
      </Box>
    </Box>
  );
};
