import { FC } from 'react';
import { Box, Button, Typography, usePopover } from '@sema4ai/components';
import { IconCloseSmall, IconLinked } from '@sema4ai/icons';
import { useDeleteConfirm } from '@sema4ai/layouts';
import { useFormContext } from 'react-hook-form';

import { Relationship } from '~/queries/semanticData';
import { DataConnectionFormSchema } from '../../form';

type Props = {
  tableName: string;
  columnName: string;
};

const RelationshipItem: FC<{ relationship: Relationship }> = ({ relationship }) => {
  const { setValue, watch } = useFormContext<DataConnectionFormSchema>();
  const onDeleteConfirm = useDeleteConfirm(
    {
      entityName: relationship.name,
      entityType: 'relationship',
    },
    [],
  );

  const allRelationships = watch('relationships');

  const onDelete = onDeleteConfirm(() => {
    if (!allRelationships) {
      return;
    }
    const newRelationships = allRelationships.filter((rel) => rel.name !== relationship.name);
    setValue('relationships', newRelationships);
  });

  return (
    <Box display="flex" alignItems="flex-start" justifyContent="space-between" gap="$8">
      <Box display="flex" flexDirection="column" gap="$2" flex="1">
        <Typography fontSize="$14" fontWeight="medium">
          {relationship.left_table} → {relationship.right_table}
        </Typography>
        <Box display="flex" flexDirection="column" gap="$2">
          {relationship.relationship_columns.map((col) => (
            <Typography key={`${col.left_column}-${col.right_column}`} color="content.subtle">
              .{col.left_column} → .{col.right_column}
            </Typography>
          ))}
        </Box>
      </Box>
      <Button
        variant="ghost-subtle"
        aria-label="Remove relationship"
        size="small"
        icon={IconCloseSmall}
        onClick={onDelete}
      />
    </Box>
  );
};

export const RelationshipsPopover: FC<Props> = ({ tableName, columnName }) => {
  const { watch } = useFormContext<DataConnectionFormSchema>();
  const allRelationships = watch('relationships');

  const relationships =
    allRelationships?.filter(
      (rel) =>
        (rel.left_table === tableName && rel.relationship_columns.some((col) => col.left_column === columnName)) ||
        (rel.right_table === tableName && rel.relationship_columns.some((col) => col.right_column === columnName)),
    ) || [];

  const { referenceRef, referenceProps, PopoverContent } = usePopover({
    hover: true,
    placement: 'top',
  });

  if (relationships.length === 0) return null;

  return (
    <>
      <Button
        ref={referenceRef}
        {...referenceProps}
        variant="ghost-subtle"
        size="small"
        aria-label="View relationships"
      >
        <IconLinked size={14} />
      </Button>
      <PopoverContent>
        <Box
          display="flex"
          flexDirection="column"
          gap="$8"
          p="$12"
          minWidth="250px"
          borderRadius="$8"
          boxShadow="medium"
          style={{ background: 'var(--sema4ai-colors-surface-default, #ffffff)' }}
        >
          <Typography fontWeight="medium" fontSize="$14">
            Relationships
          </Typography>
          {relationships.map((rel) => (
            <RelationshipItem key={rel.name} relationship={rel} />
          ))}
        </Box>
      </PopoverContent>
    </>
  );
};
