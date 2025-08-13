import { Box, Select } from '@sema4ai/components';

// Mock document types and stages
const mockDocumentTypes = [
  { label: 'Invoices', value: 'invoices' },
  { label: 'Contracts', value: 'contracts' },
  { label: 'Reports', value: 'reports' },
];

const mockStages = [
  { label: 'Initial Processing', value: 'initial' },
  { label: 'Review', value: 'review' },
  { label: 'Final Processing', value: 'final' },
];

export const WizardStep4 = () => {
  return (
    <Box display="flex" flexDirection="column" gap="$24">
      <Box>
        <h3>Document Triggers</h3>
        <p>Configure which document types will trigger this agent.</p>
      </Box>

      <Box>
        <Select
          label="Document Type"
          description="Every new document of the selected type will trigger the agent."
          items={mockDocumentTypes}
          onChange={(value) => {
            console.log('Document type selected:', value);
          }}
        />
      </Box>

      <Box>
        <Select
          label="Processing Stage"
          description="The stage in the document workflow where this agent will be triggered."
          items={mockStages}
          onChange={(value) => {
            console.log('Stage selected:', value);
          }}
        />
      </Box>
    </Box>
  );
};
