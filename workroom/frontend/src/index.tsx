import { createRoot } from 'react-dom/client';
import { Agentation } from 'agentation';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

import { setupPdfWorker } from '~/components/DocumentIntelligence/setupPdfWorker';

import { App } from './App';

setupPdfWorker(pdfjsWorker);

const root = createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <>
    {import.meta.env.DEV && <Agentation />}
    <App />
  </>,
);
