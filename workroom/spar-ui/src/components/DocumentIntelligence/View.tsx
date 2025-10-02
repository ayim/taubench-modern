import { FC, useState } from 'react';
import { useListModelsQuery, useParseDocumentMutation } from '../../queries/documentIntelligence';

interface Props {
  agentId: string;
  threadId: string;
  flowType: 'parse' | 'createModel';
  fileRef: File;
}

interface ParsedDocument {
  [key: string]: unknown;
}

export const DocumentIntelligenceView: FC<Props> = ({ agentId, threadId, flowType, fileRef }) => {
  const [parsedDocument, setParsedDocument] = useState<ParsedDocument | null>(null);

  const { data, isLoading, isError, error } = useListModelsQuery({});
  const {
    mutateAsync: parseDocumentAsync,
    isPending: isParsing,
    isError: isParseDocumentError,
    error: parseDocumentError
  } = useParseDocumentMutation({});

  const handleParse = async () => {
    try {
      const result = await parseDocumentAsync({
        threadId,
        formData: fileRef
      });
      setParsedDocument(result);
      // eslint-disable-next-line no-console
      console.log('Parse result:', result);
    } catch (parseError) {
      // eslint-disable-next-line no-console
      console.error('Parse failed:', parseError);
    }
  };

  if (isLoading) {
    return <div>Loading Document Intelligence models...</div>;
  }

  if (isError) {
    return <div>Error loading models: {error?.message}</div>;
  }

  return (
    <div>
      <h2>Document Intelligence v2</h2>
      <p>Agent ID: {agentId}</p>
      <p>Thread ID: {threadId}</p>
      <p>Flow Type: {flowType}</p>
      <p>File: {fileRef.name}</p>

      <h3 style={{ margin: '10px 0'}}>Modal is working!</h3>
      <p>This confirms the div2_ prefix logic and modal rendering work correctly.</p>
      <div style={{ margin: '10px 0', padding: '10px 20px' }}>
        <h4>Available Models:</h4>
        <ul>
          {Array.isArray(data) && data.map((model: { name: string }) => (
            <li key={model.name}>{model.name}</li>
          ))}
        </ul>
      </div>

      <button
        type="button"
        onClick={handleParse}
        disabled={isParsing}
        style={{ margin: '10px 0', padding: '10px 20px' }}
      >
        {isParsing ? 'Parsing Document...' : 'Parse Document'}
      </button>

      {isParseDocumentError && (
        <div style={{ color: 'red' }}>
          Parse Error: {parseDocumentError?.message}
        </div>
      )}

      {parsedDocument && (
        <div>
          <h4>Parsed Document:</h4>
          <pre style={{ background: '#f5f5f5', padding: '10px', overflow: 'auto' }}>
            {JSON.stringify(parsedDocument, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
