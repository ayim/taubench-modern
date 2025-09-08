import { Box, Column, Table, TableRowProps, Button } from '@sema4ai/components';
import { FC } from 'react';
import { Link, useNavigate } from '@tanstack/react-router';
import { IconCheckCircle, IconWarningTriangle, IconPause, IconShare, IconStatusNew, IconTrash } from '@sema4ai/icons';
import { useTenantContext } from '~/lib/tenantContext';

interface IAgentData {
  id: string;
  name: string;
  state: string;
  lastInteraction: string;
}

interface RowItemProps {
  tenantId: string;
  columns: Column[];
}

interface CellProps {
  data: string | number | null;
}

// function to display the icon for the state column based on the status
const renderStateIcon = (state: string) => {
  switch (state) {
    case 'Ready':
      return <IconCheckCircle color="#141414" />;
    case 'Paused':
      return <IconPause color="#141414" />;
    case 'Failed':
      return <IconWarningTriangle color="#BE1111" />;
    default:
      return <IconStatusNew />;
  }
};

const CustomCell: FC<CellProps> = ({ data }) => {
  return <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">{data}</Table.Cell>;
};

const RowItem: FC<TableRowProps<IAgentData, RowItemProps>> = ({ rowData, props }) => {
  const { tenantId } = props;
  const navigate = useNavigate({ from: '/tenants/$tenantId/agents' });
  const { features } = useTenantContext();

  return (
    <Table.Row>
      {/* Agent Name column with a clickable action */}
      <Table.Cell>
        <Link
          to="/tenants/$tenantId/$agentId"
          params={{ tenantId, agentId: rowData.id }}
          className="cursor-pointer flex flex-row items-center gap-1 truncate"
        >
          <p className="whitespace-nowrap overflow-hidden text-ellipsis">{rowData.name}</p>
          <Button aria-label="Agent Dashboard Details" icon={IconShare} size="small" variant="ghost" />
        </Link>
      </Table.Cell>

      {/* State with icon */}
      <Table.Cell className="max-w-40 whitespace-nowrap overflow-hidden text-ellipsis">
        <Box display="flex" alignItems="center" justifyContent="flex-start" gap="5px">
          {renderStateIcon(rowData.state)} {rowData.state}
        </Box>
      </Table.Cell>

      {/* Last Interaction */}
      <CustomCell data={rowData.lastInteraction} />

      {/* Actions */}
      {features.deploymentWizard.enabled && (
        <Table.Cell>
          <Button
            aria-label="Delete agent"
            icon={IconTrash}
            size="small"
            variant="ghost"
            onClick={() =>
              navigate({
                to: '/tenants/$tenantId/agents',
                params: { tenantId },
                search: (prev) => ({ ...prev, deleteAgentId: rowData.id }),
              })
            }
          />
        </Table.Cell>
      )}
    </Table.Row>
  );
};

export default RowItem;
