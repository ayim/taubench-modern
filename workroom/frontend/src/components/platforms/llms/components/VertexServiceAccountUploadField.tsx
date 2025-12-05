import { Box, Button, FileItem } from '@sema4ai/components';
import { IconFileText, IconUpload } from '@sema4ai/icons';
import { FC, useRef, useState } from 'react';
import { Controller, useFormContext } from 'react-hook-form';

export const VertexServiceAccountUploadField: FC = () => {
  const { control } = useFormContext();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const uploadRequestIdRef = useRef(0);

  const startNewUploadRequest = () => {
    uploadRequestIdRef.current += 1;
    return uploadRequestIdRef.current;
  };

  const clearSelection = (onChange: (value: string | null) => void) => {
    setFileName(null);
    setIsUploading(false);
    startNewUploadRequest();
    if (inputRef.current) {
      inputRef.current.value = '';
    }
    onChange(null);
  };

  return (
    <Controller
      name="google_vertex_service_account_json"
      control={control}
      render={({ field, fieldState }) => (
        <Box display="flex" flexDirection="column" gap="$3">
          <Box display="flex" justifyContent="space-between" alignItems="center" gap="$4">
            <Box as="label" htmlFor="vertex-service-account-upload" fontWeight="$semibold">
              Service Account JSON
            </Box>
            <Button
              type="button"
              variant="outline"
              icon={IconUpload}
              onClick={() => inputRef.current?.click()}
              disabled={isUploading}
            >
              {fileName || field.value ? 'Replace JSON File' : 'Upload JSON File'}
            </Button>
          </Box>
          <input
            ref={inputRef}
            id="vertex-service-account-upload"
            type="file"
            accept="application/json"
            style={{ display: 'none' }}
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) {
                clearSelection(field.onChange);
                return;
              }
              const uploadRequestId = startNewUploadRequest();
              setIsUploading(true);
              setFileName(file.name);
              try {
                const fileContents = await file.text();
                if (uploadRequestIdRef.current === uploadRequestId) {
                  field.onChange(fileContents);
                }
              } finally {
                if (uploadRequestIdRef.current === uploadRequestId) {
                  setIsUploading(false);
                }
              }
            }}
          />
          {fileName || field.value ? (
            <FileItem
              label={fileName ?? 'Service account JSON configured'}
              description={
                fileName
                  ? 'Ready to upload. Submit the form to save this credential.'
                  : 'A service account is already configured. Upload a new JSON file to replace it.'
              }
              icon={IconFileText}
              uploading={isUploading}
              onCloseClick={() => clearSelection(field.onChange)}
            />
          ) : (
            <Box as="p" fontSize="$sm" color="$gray-70">
              Upload the Google Cloud service account JSON used for Vertex AI requests.
            </Box>
          )}
          {fieldState.error && (
            <Box as="p" fontSize="$sm" color="$danger-60">
              {fieldState.error.message}
            </Box>
          )}
        </Box>
      )}
    />
  );
};
