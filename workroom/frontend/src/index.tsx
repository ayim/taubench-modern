import { createRoot } from 'react-dom/client';
import { setupPdfWorker } from '@sema4ai/spar-ui';
import { Agentation } from 'agentation';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { App } from './App';

setupPdfWorker(pdfjsWorker);

const root = createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <>
    {import.meta.env.DEV && <Agentation />}
    <App />
  </>,
);
