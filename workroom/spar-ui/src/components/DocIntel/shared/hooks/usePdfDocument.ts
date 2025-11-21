import { useState, useEffect, useCallback } from 'react';
import { pdfjs } from 'react-pdf';

export type PDFDocumentProxy = pdfjs.PDFDocumentProxy;
export type PDFPageProxy = pdfjs.PDFPageProxy;

interface UsePdfDocumentProps {
  file: File;
}

export const usePdfDocument = ({ file }: UsePdfDocumentProps) => {
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [numPages, setNumPages] = useState<number>(0);
  const [scale, setScale] = useState<number>(1.5); // Default 150% zoom
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfBlob, setPdfBlob] = useState<Blob | null>(null);
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
  const onDocumentLoadSuccess = useCallback((document: PDFDocumentProxy) => {
    setNumPages(document.numPages);
    setCurrentPage(1);
  }, []);

  const onDocumentLoadError = useCallback((err: Error) => {
    setError(`Failed to load PDF: ${err.message}`);
  }, []);

  // Page rendering handlers
  const onPageLoadSuccess = useCallback(
    (page: PDFPageProxy) => {
      const viewport = page.getViewport({ scale: 1 });
      setPageWidth(viewport.width * scale);
      setPageHeight(viewport.height * scale);
    },
    [scale],
  );

  // Navigation handlers
  const goToPage = useCallback(
    (pageNumber: number) => {
      if (pageNumber >= 1 && pageNumber <= numPages) {
        setCurrentPage(pageNumber);
      }
    },
    [numPages],
  );

  const changeScale = useCallback((newScale: number) => {
    const clampedScale = Math.max(0.5, Math.min(3.0, newScale));
    setScale(clampedScale);
  }, []);

  return {
    // State
    currentPage,
    numPages,
    scale,
    zoomPercentage,
    isLoading,
    error,
    pdfBlob,
    pageWidth,
    pageHeight,
    isPdf,
    // Handlers
    loadPdfFromFile,
    onDocumentLoadSuccess,
    onDocumentLoadError,
    onPageLoadSuccess,
    goToPage,
    changeScale,
  };
};
