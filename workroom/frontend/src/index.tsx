import { createRoot } from 'react-dom/client';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { init as initFullStory } from '@fullstory/browser';

import { setupPdfWorker } from '~/components/DocumentIntelligence/setupPdfWorker';

import { App } from './App';

setupPdfWorker(pdfjsWorker);

if (import.meta.env.VITE_3RDPARTY_FULLSTORY_ORG_ID) {
  initFullStory({
    orgId: import.meta.env.VITE_3RDPARTY_FULLSTORY_ORG_ID,
  });
}

const root = createRoot(document.getElementById('root') as HTMLElement);
root.render(<App />);
