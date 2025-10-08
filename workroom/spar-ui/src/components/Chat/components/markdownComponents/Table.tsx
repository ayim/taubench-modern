import { Box, Button, Table as TableComponent, TableProps, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';

const Container = styled(Box)`
  position: relative;
  margin-bottom: ${({ theme }) => theme.space.$24};

  &:before {
    content: '';
    position: absolute;
    top: 0;
    left: -40px;
    width: 40px;
    height: 100%;
  }

  > button {
    position: absolute;
    top: 0;
    left: -${({ theme }) => theme.space.$40};
    display: none;
  }

  &:hover {
    > button {
      display: block;
    }
  }
`;

type Props = TableProps & {
  raw: string;
};

export const Table: FC<Props> = ({ columns, data, raw }) => {
  const { onCopyToClipboard, copiedToClipboard } = useClipboard();

  return (
    <Container>
      <Button
        variant="ghost-subtle"
        icon={copiedToClipboard ? IconCheck2 : IconCopy}
        aria-label="Copy table"
        onClick={onCopyToClipboard(raw)}
      />
      <TableComponent columns={columns} data={data} />
    </Container>
  );
};
