import { FC, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { ThreadAttachmentContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Checkbox, Form, Typography } from '@sema4ai/components';
import { IconFilePlus } from '@sema4ai/icons';
import { useNavigate, useParams } from '../../hooks';
import {
  DataFrameInspectFile,
  useCreateDataFrameFromFileMutation,
  useDataFramesInspectFileQuery,
  useDataFramesQuery,
} from '../../queries/dataFrames';
import { ThreadFiles, useThreadFileQuery } from '../../queries/threads';
import { getIsSupportedDataFrameFile } from './utils';

type UploadedFile = ThreadFiles[number];
type DataFrameInspectResult = Omit<DataFrameInspectFile[number], 'data_frame_id' | 'description'>;

interface SharedProps {
  agentId: string;
  threadId: string;
  file: UploadedFile;
}

const DataFrameFormContent = ({
  agentId,
  threadId,
  inspectResults,
  alreadyInspectedSheets,
  file,
}: SharedProps & {
  inspectResults: DataFrameInspectResult[];
  alreadyInspectedSheets: string[];
}) => {
  const navigate = useNavigate();
  const { mutateAsync: createDataFrameAsync } = useCreateDataFrameFromFileMutation({});

  const {
    register,
    handleSubmit,
    formState: { isSubmitting, isSubmitSuccessful },
  } = useForm<{ spreadsheets: { [key: string]: boolean } }>();
  const onSubmit = (data: { spreadsheets: { [key: string]: boolean } }) => {
    const enabledSheetNames = Object.keys(data.spreadsheets).filter((sheetName) => data.spreadsheets[sheetName]);

    if (enabledSheetNames.length === 0) return null;
    return Promise.allSettled([
      ...enabledSheetNames.map((sheetName) => createDataFrameAsync({ threadId, fileId: file.file_id, sheetName })),
    ]).then(() => navigate({ to: '/thread/$agentId/$threadId/data-frames', params: { threadId, agentId } }));
  };

  const actionDone = isSubmitting || isSubmitSuccessful || alreadyInspectedSheets.length > 0;
  return (
    <Box>
      <Form onSubmit={handleSubmit(onSubmit)}>
        <Form.Fieldset>
          <Checkbox.Group>
            {inspectResults.map((result) =>
              typeof result.sheet_name === 'string' && alreadyInspectedSheets.includes(result.sheet_name) ? (
                <Checkbox key={result.sheet_name} label={result.sheet_name} checked disabled />
              ) : (
                <Checkbox
                  disabled={actionDone}
                  key={result.sheet_name}
                  label={result.sheet_name}
                  {...register(`spreadsheets.${result.sheet_name}`)}
                />
              ),
            )}
          </Checkbox.Group>
        </Form.Fieldset>
        <Box display="flex" alignItems="center" gap="$4">
          <Button
            type="submit"
            icon={IconFilePlus}
            variant={actionDone ? 'primary' : 'outline'}
            disabled={actionDone}
            round
          >
            Use only these sheets
          </Button>
        </Box>
      </Form>
    </Box>
  );
};

const SimplifiedDataFrameForm: FC<SharedProps & { dataFrameCreated: boolean }> = ({
  agentId,
  threadId,
  file,
  dataFrameCreated,
}) => {
  const navigate = useNavigate();
  const { mutateAsync: createDataFrameAsync, isPending } = useCreateDataFrameFromFileMutation({});
  const handleCreateDataFrame = () =>
    createDataFrameAsync({ threadId, fileId: file.file_id }).then(() =>
      navigate({ to: '/thread/$agentId/$threadId/data-frames', params: { threadId, agentId } }),
    );

  const actionDone = isPending || dataFrameCreated;
  return (
    <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
      <Typography>Would you like to create a new data frame?</Typography>
      <Box display="flex" alignItems="center" gap="$4">
        <Button
          onClick={handleCreateDataFrame}
          icon={IconFilePlus}
          variant={actionDone ? 'primary' : 'outline'}
          disabled={actionDone}
          round
        >
          Create a Data Frame
        </Button>
      </Box>
    </Box>
  );
};

const DataFrameSheetContent = ({
  agentId,
  threadId,
  file,
  alreadyInspectedSheets,
  dataFrameFromFileExists,
}: SharedProps & { dataFrameFromFileExists: boolean; alreadyInspectedSheets: string[] }) => {
  const {
    data: inspectResults = [],
    isError,
    isLoading,
  } = useDataFramesInspectFileQuery({ threadId, fileId: file.file_id });

  if (isError) {
    return (
      <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
        <Typography>There was an error when inspecting the file.</Typography>
      </Box>
    );
  }

  if (isLoading) {
    return null;
  }

  const shouldDisplaySimplifiedDataFrameForm = inspectResults.length === 0 || inspectResults.length === 1;
  if (shouldDisplaySimplifiedDataFrameForm) {
    return (
      <SimplifiedDataFrameForm
        agentId={agentId}
        threadId={threadId}
        file={file}
        dataFrameCreated={dataFrameFromFileExists}
      />
    );
  }

  return (
    <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
      <Typography>There are {inspectResults.length} sheets in this file. Which one would you like to use?</Typography>

      <DataFrameFormContent
        agentId={agentId}
        threadId={threadId}
        alreadyInspectedSheets={alreadyInspectedSheets}
        inspectResults={inspectResults}
        file={file}
      />
    </Box>
  );
};

const DataFrameSheetContainer: FC<SharedProps> = ({ file, threadId, agentId }) => {
  const { data: dataFrames = [] } = useDataFramesQuery({ threadId });

  const { dataFrameFromFileExists, alreadyInspectedSheets } = useMemo<{
    dataFrameFromFileExists: boolean;
    alreadyInspectedSheets: string[];
  }>(() => {
    const fileDataFrame = dataFrames.findIndex((dataFrame) => dataFrame?.file_id === file.file_id);
    if (fileDataFrame === -1) {
      return {
        dataFrameFromFileExists: false,
        alreadyInspectedSheets: [],
      };
    }

    const inspectedSheets = dataFrames
      .filter((dataFrame) => dataFrame?.file_id === file.file_id && typeof dataFrame.sheet_name === 'string')
      .map((dataFrame) => dataFrame.sheet_name as string);

    return {
      dataFrameFromFileExists: true,
      alreadyInspectedSheets: inspectedSheets,
    };
  }, [dataFrames, file.file_id]);

  return (
    <DataFrameSheetContent
      agentId={agentId}
      threadId={threadId}
      dataFrameFromFileExists={dataFrameFromFileExists}
      alreadyInspectedSheets={alreadyInspectedSheets}
      file={file}
    />
  );
};

export const DataFrameFormContainer: FC<{ threadId: string; fileRef: string; agentId: string }> = ({
  agentId,
  threadId,
  fileRef,
}) => {
  const { data: file } = useThreadFileQuery({ threadId, fileRef });
  if (!file) return null;

  return <DataFrameSheetContainer file={file} threadId={threadId} agentId={agentId} />;
};

type Props = {
  content: ThreadAttachmentContent;
};

export const DataFrameForm: FC<Props> = ({ content }) => {
  const { threadId, agentId } = useParams('/thread/$agentId/$threadId');
  const { isSupportedFile, fileRef } = useMemo(() => {
    const isSupportedFileMimeType = getIsSupportedDataFrameFile({ mime_type: content.mime_type });
    return {
      isSupportedFile: isSupportedFileMimeType,
      fileRef: content.name,
    };
  }, [content.mime_type, content.name]);

  if (!isSupportedFile || fileRef === undefined) return null;
  return <DataFrameFormContainer fileRef={fileRef} threadId={threadId} agentId={agentId} />;
};
