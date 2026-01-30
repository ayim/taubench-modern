import { createRoot } from 'react-dom/client';
import { Agentation } from 'agentation';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { init as initFullStory } from '@fullstory/browser';

import { setupPdfWorker } from '~/components/DocumentIntelligence/setupPdfWorker';

import { App } from './App';

setupPdfWorker(pdfjsWorker);

if (import.meta.env.PROD) {
  initFullStory({
    orgId: import.meta.env.SEMA4AI_3RDPARTY_FULLSTORY_ORG_ID,
  });
}

const root = createRoot(document.getElementById('root') as HTMLElement);
root.render(
  <>
    {import.meta.env.DEV && <Agentation />}
    <App />
  </>,
);
