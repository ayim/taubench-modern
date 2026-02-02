import { styled } from '@sema4ai/theme';
import { FC } from 'react';

import { DropzoneConfig } from '@sema4ai/components';
import { AddFiles } from './components/AddFiles';
import { FilesList } from './components/FilesList';

type Props = {
  threadId: string;
  agentId: string;
  /**
   * Options to control the file acceptance and behavior of the dropzone
   * @see https://sema4ai-design-system.pages.dev/component/dropzone
   */
  dropzoneOptions?: DropzoneConfig;
};

const Container = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$20};
  height: 100%;
  overflow: hidden;
  padding: ${({ theme }) => theme.space.$8};

  & > *:nth-child(1) {
    flex: 0 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  & > *:nth-child(2) {
    flex: 1 1 auto;
    min-height: 100px;
  }
`;

export const FilesView: FC<Props> = ({ threadId, agentId, dropzoneOptions }) => {
  return (
    <Container>
      <FilesList agentId={agentId} threadId={threadId} />
      <AddFiles threadId={threadId} agentId={agentId} dropzoneOptions={dropzoneOptions} />
    </Container>
  );
};
