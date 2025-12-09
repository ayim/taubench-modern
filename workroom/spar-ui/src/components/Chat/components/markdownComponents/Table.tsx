import { Box, Button, Table as TableComponent, TableProps, useClipboard } from '@sema4ai/components';
import { IconCheck2, IconCopy } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';

const Container = styled(Box)`
  position: relative;
  margin: 0 -${({ theme }) => theme.space.$8};

  &:before {
    content: '';
    position: absolute;
    top: 1px;
    right: 0;
    width: 40px;
    height: 40px;
  }

  > button {
    position: absolute;
    top: 2px;
    right: 2px;
    display: none;
    z-index: 100;
  }

  &:hover {
    > button {
      display: block;
      background-color: ${({ theme }) => theme.colors.background.primary.color};
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
      <TableComponent columns={columns} data={data} size="small" rowCount={50} />
    </Container>
  );
};
