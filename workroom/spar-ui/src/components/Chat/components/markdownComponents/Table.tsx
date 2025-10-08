import { Box, MarkdownParserRules, Table as TableComponent } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

const Container = styled(Box)`
  position: relative;

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

export const Table: MarkdownParserRules['table'] = ({ header, rows }) => {
  const columns = header.map((column) => ({
    id: column.text,
    title: column.text,
  }));

  const data = rows.map((row) => {
    return Object.fromEntries(columns.map((column, index) => [column.id, row[index].text]));
  });

  return (
    <Container>
      <TableComponent columns={columns} data={data} />
    </Container>
  );
};
