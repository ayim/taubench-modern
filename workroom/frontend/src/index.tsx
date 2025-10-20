import { createRoot } from 'react-dom/client';
import { setupPdfWorker } from '@sema4ai/spar-ui';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { App } from './App';

setupPdfWorker(pdfjsWorker);

const root = createRoot(document.getElementById('root') as HTMLElement);
root.render(<App />);
