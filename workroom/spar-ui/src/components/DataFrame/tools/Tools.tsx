import { FC, useCallback, useEffect, useMemo, useState } from 'react';
import { ThreadToolUsageContent } from '@sema4ai/agent-server-interface';
import { Box, Button, Checkbox, Form, Typography } from '@sema4ai/components';
import { IconFilePlus, IconClose } from '@sema4ai/icons';
import { useForm } from 'react-hook-form';
import { useMessageStream, useParams } from '../../../hooks';
import { DataFrameInspectFile, useDataFramesInspectFileQuery, useDataFramesQuery } from '../../../queries/dataFrames';
import { ThreadFiles, useThreadFilesQuery } from '../../../queries/threads';
import { getIsSupportedDataFrameFile } from './utils';

type UploadedFile = ThreadFiles[number];
type DataFrameInspectResult = Omit<DataFrameInspectFile[number], 'data_frame_id' | 'description'>;

const CREATE_DATA_FRAME_RESPONSE_PREFIX = 'Create Data Frame';
const CANCEL_DATA_FRAME_RESPONSE_PREFIX = 'Cancel creation of Data Frame';

interface SharedProps {
  threadId: string;
  agentId: string;
  tool: ThreadToolUsageContent;
}

const DataFrameForm = ({
  threadId,
  agentId,
  inspectResults,
  alreadyInspectedSheets,
  file,
  tool,
}: SharedProps & {
  inspectResults: DataFrameInspectResult[];
  file: UploadedFile;
  alreadyInspectedSheets: string[];
}) => {
  const isCreateResponse = tool.result?.includes(CREATE_DATA_FRAME_RESPONSE_PREFIX);
  const isCancelResponse = tool.result?.includes(CANCEL_DATA_FRAME_RESPONSE_PREFIX);
  const hasResponse = !!tool.result;

  const { sendClientToolMessage } = useMessageStream({
    agentId,
    threadId,
  });

  const handleCreateDataFrame = useCallback(
    (response: string) => {
      sendClientToolMessage(tool, response);
    },
    [threadId, tool],
  );

  const handleCancel = useCallback(() => {
    sendClientToolMessage(tool, CANCEL_DATA_FRAME_RESPONSE_PREFIX);
  }, [threadId, tool]);

  const {
    register,
    handleSubmit,
    formState: { isSubmitting, isSubmitSuccessful },
  } = useForm<{ spreadsheets: { [key: string]: boolean } }>();
  const onSubmit = (data: { spreadsheets: { [key: string]: boolean } }) => {
    const enabledSheetNames = Object.keys(data.spreadsheets).filter((sheetName) => data.spreadsheets[sheetName]);
    if (enabledSheetNames.length === 0) {
      handleCancel();
    } else if (enabledSheetNames.length === 1) {
      handleCreateDataFrame(
        `${CREATE_DATA_FRAME_RESPONSE_PREFIX} from "${file.file_ref}" and "${data.spreadsheets[0]}" sheet`,
      );
    } else {
      handleCreateDataFrame(
        `${CREATE_DATA_FRAME_RESPONSE_PREFIX}s from "${file.file_ref}" and "${enabledSheetNames.join('", "')}" sheets`,
      );
    }
  };

  const isPending = isSubmitting || isSubmitSuccessful;
  const isDisabled = isPending || hasResponse;
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
                  disabled={isDisabled}
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
            variant={isCreateResponse || isPending ? 'primary' : 'outline'}
            disabled={isDisabled}
            round
          >
            Use only these sheets
          </Button>
          <Button
            onClick={handleCancel}
            icon={IconClose}
            variant={isCancelResponse ? 'primary' : 'outline'}
            disabled={isDisabled}
            round
          >
            Cancel
          </Button>
        </Box>
      </Form>
    </Box>
  );
};

const SimplifiedDataFrameForm: FC<SharedProps> = ({ threadId, tool, agentId }) => {
  const [isPending, setIsPending] = useState(false);

  const isCreateResponse = tool.result?.includes(CREATE_DATA_FRAME_RESPONSE_PREFIX);
  const isCancelResponse = tool.result?.includes(CANCEL_DATA_FRAME_RESPONSE_PREFIX);
  const hasResponse = !!tool.result;

  const { sendClientToolMessage } = useMessageStream({
    agentId,
    threadId,
  });

  const handleAction = useCallback(
    async (result: string) => {
      await sendClientToolMessage(tool, result);
      setIsPending(true);
    },
    [threadId, tool],
  );

  const handleCreateDataFrame = useCallback(() => handleAction(CREATE_DATA_FRAME_RESPONSE_PREFIX), [handleAction]);
  const handleCancel = useCallback(() => handleAction(CANCEL_DATA_FRAME_RESPONSE_PREFIX), [handleAction]);

  const isDisabled = isPending || hasResponse;
  return (
    <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
      <Typography>Would you like to create a new data frame?</Typography>
      <Box display="flex" alignItems="center" gap="$4">
        <Button
          onClick={handleCreateDataFrame}
          icon={IconFilePlus}
          variant={isCreateResponse ? 'primary' : 'outline'}
          disabled={isDisabled}
          round
        >
          Create a Data Frame
        </Button>
        <Button
          onClick={handleCancel}
          icon={IconClose}
          variant={isCancelResponse ? 'primary' : 'outline'}
          disabled={isDisabled}
          round
        >
          Cancel
        </Button>
      </Box>
    </Box>
  );
};

const DataFrameSheetContent = ({
  threadId,
  agentId,
  file,
  alreadyInspectedSheets,
  tool,
}: SharedProps & { file: UploadedFile; alreadyInspectedSheets: string[] }) => {
  const { data: inspectResults = [], isError } = useDataFramesInspectFileQuery({ threadId, fileId: file.file_id });

  if (isError) {
    return (
      <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
        <Typography>There was an error when inspecting the file.</Typography>
      </Box>
    );
  }

  const shouldDisplaySimplifiedDataFrameForm = inspectResults.length === 0 || inspectResults.length === 1;
  if (shouldDisplaySimplifiedDataFrameForm) {
    return <SimplifiedDataFrameForm threadId={threadId} agentId={agentId} tool={tool} />;
  }

  return (
    <Box display="flex" flexDirection="column" width="100%" height="100%" gap="$8" pt="$12">
      <Typography>There are {inspectResults.length} sheets in this file. Which one would you like to use?</Typography>

      <DataFrameForm
        threadId={threadId}
        agentId={agentId}
        alreadyInspectedSheets={alreadyInspectedSheets}
        inspectResults={inspectResults}
        file={file}
        tool={tool}
      />
    </Box>
  );
};

const DataFrameSheetContainer: FC<{
  file: UploadedFile;
  tool: ThreadToolUsageContent;
  threadId: string;
  agentId: string;
}> = ({ file, tool, threadId, agentId }) => {
  const { data: dataFrames = [] } = useDataFramesQuery({ threadId });

  const alreadyInspectedSheets = useMemo<string[]>(
    () =>
      dataFrames
        .filter((dataFrame) => dataFrame?.file_id === file.file_id && typeof dataFrame.sheet_name === 'string')
        .map((dataFrame) => dataFrame.sheet_name as string),
    [dataFrames, file.file_id],
  );

  return (
    <DataFrameSheetContent
      threadId={threadId}
      agentId={agentId}
      alreadyInspectedSheets={alreadyInspectedSheets}
      file={file}
      tool={tool}
    />
  );
};

export const DataFrameConfirmParseDataFrameFile: React.FC<{ tool: ThreadToolUsageContent }> = ({ tool }) => {
  const { threadId, agentId } = useParams('/thread/$agentId/$threadId');

  /**
   * TODO: get exact file
   * - issue with this logic is that we get all thread files and assume that the last one is unprocessed data frame file
   *
   * We need to tie tool call initiator with specific file id. Two options here:
   * 1. pass file id as argument to tool call
   * 2. smarter context for related chat messages?
   */
  const { data: threadFiles = [] } = useThreadFilesQuery({ threadId });
  const latestFile = threadFiles[threadFiles.length - 1];

  if (!getIsSupportedDataFrameFile(latestFile)) return null;

  return (
    <DataFrameSheetContainer
      key={`data-frames-confirm-creation-${tool.content_id}`}
      tool={tool}
      file={latestFile}
      threadId={threadId}
      agentId={agentId}
    />
  );
};

const DATA_FRAME_REFETCH_GRACE_PERIOD = 500;

export const DataFrameCallbackDataFrameCreation: React.FC<{ tool: ThreadToolUsageContent }> = ({ tool }) => {
  const { threadId } = useParams('/thread/$agentId/$threadId');
  const { refetch } = useDataFramesQuery({ threadId });

  const isComplete = tool.complete;
  useEffect(() => {
    if (isComplete) {
      setTimeout(() => {
        refetch();
      }, DATA_FRAME_REFETCH_GRACE_PERIOD);
    }
  }, [isComplete, refetch]);

  return null;
};
