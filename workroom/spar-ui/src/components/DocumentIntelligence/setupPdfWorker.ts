import { pdfjs } from 'react-pdf';

/**
 * Configure the PDF.js worker for DocumentIntelligence components.
 * This must be called before rendering any DocumentIntelligence components.
 *
 * @param workerSrc - Path to the PDF.js worker file
 *
 * @example
 * // Vite (Spar / Work Room)
 * import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
 * setupPdfWorker(pdfjsWorker);
 *
 * @example
 * // Webpack (Studio)
 * const pdfjsWorker = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();
 * setupPdfWorker(pdfjsWorker);
 */
export const setupPdfWorker = (workerSrc: string): void => {
  pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
};
