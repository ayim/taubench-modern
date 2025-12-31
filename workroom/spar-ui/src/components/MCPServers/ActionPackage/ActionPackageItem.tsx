import type { FC } from 'react';
import { Box, Badge } from '@sema4ai/components';
import { IconStatusCompleted, IconStatusTimeout, IconMcp } from '@sema4ai/icons';
import { useFormContext } from 'react-hook-form';
import { styled } from '@sema4ai/theme';

import { AgentPackageInspectionResponse } from '../../../queries/agentPackageInspection';
import { ActionSecrets } from './ActionSecrets';
import { parseWhitelist, getUniqueSecretNames } from './actionPackageUtils';

const Container = styled.div`
  display: grid;
  grid-template-columns: 28px auto;
  gap: ${({ theme }) => theme.sizes.$16};

  > div {
    position: relative;

    &:first-child {
      padding-top: 34px;
    }

    &::before {
      display: block;
      position: absolute;
      top: 0;
      content: '';
      width: 1px;
      height: 100%;
      position: absolute;
      left: 50%;
      border-left: 1px ${({ theme }) => theme.colors.border.inverted.color} dashed;
    }
  }

  &:first-child {
    padding-top: ${({ theme }) => theme.space.$16};

    > div::before {
      top: -12px;
      height: calc(100% + 12px);
    }

    > div:first-child::after {
      display: block;
      position: absolute;
      top: -18px;
      content: '';
      width: 7px;
      height: 7px;
      border-radius: 7px;
      position: absolute;
      left: calc(50% - 3px);
      border: 1px ${({ theme }) => theme.colors.border.inverted.color} solid;
      background: ${({ theme }) => theme.colors.background.primary.color};
    }
  }

  &:last-child {
    > section {
      position: relative;
      &::after {
        display: block;
        position: absolute;
        bottom: 0px;
        left: -33px;
        content: '';
        width: 7px;
        height: 7px;
        border-radius: 7px;
        position: absolute;
        border: 1px ${({ theme }) => theme.colors.border.inverted.color} solid;
        background: ${({ theme }) => theme.colors.background.primary.color};
      }
    }
  }
`;

const StatusIcon = styled.div<{ $ready?: boolean }>`
  position: relative;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: ${({ theme }) => theme.sizes.$4};
  background: ${({ theme }) => theme.colors.background.primary.color};
  color: ${({ $ready, theme }) => ($ready ? theme.colors.green80 : theme.colors.yellow80)};
`;

export const ActionPackageItem: FC<{
  actionPackage: NonNullable<NonNullable<AgentPackageInspectionResponse>['action_packages']>[number];
}> = ({ actionPackage }) => {
  const { watch } = useFormContext();
  const { agentPackageSecrets } = watch();

  const whitelist = parseWhitelist(actionPackage.whitelist);

  const displayedActions =
    actionPackage.actions?.filter((action) => {
      if (!whitelist) return true;
      return whitelist.includes(action.name);
    }) || [];

  const uniqueSecrets = getUniqueSecretNames(actionPackage, whitelist);

  const isValid = Array.from(uniqueSecrets).every((secretName) => {
    const value = agentPackageSecrets?.[secretName];
    return value && typeof value === 'string' && value.trim() !== '';
  });

  return (
    <Container>
      <Box>
        <StatusIcon $ready={isValid}>
          {isValid ? (
            <Badge
              aria-description="Completed"
              variant="success"
              iconColor="background.success"
              icon={IconStatusCompleted}
            />
          ) : (
            <Badge
              aria-description="Incomplete"
              variant="warning"
              iconColor="background.notification"
              icon={IconStatusTimeout}
            />
          )}
        </StatusIcon>
      </Box>
      <Box as="section" pt="$8" pb="$24">
        <Box borderColor={isValid ? 'border.subtle' : 'border.notification'} borderRadius="$16" p="$24">
          <Box mb="$16">
            <Box display="flex" alignItems="center" gap="$8" mb="$8">
              <Box as="h3" fontSize="$18" fontWeight="medium">
                {actionPackage.name}
              </Box>
              {actionPackage.version && <Badge variant="info" label={`v${actionPackage.version}`} />}
            </Box>
            {actionPackage.description && (
              <Box fontSize="$14" color="content.subtle">
                {actionPackage.description}
              </Box>
            )}
          </Box>

          {displayedActions.length > 0 && (
            <Box mb="$16">
              <Box mb="$8" fontSize="$14" fontWeight="medium">
                Actions ({displayedActions.length})
              </Box>
              <Box display="flex" gap="$8" flexWrap="wrap">
                {displayedActions.map((action) => (
                  <Box
                    key={action.name}
                    display="flex"
                    alignItems="center"
                    gap="$4"
                    borderColor="border.subtle"
                    borderRadius="$8"
                    p="$8"
                    fontSize="$14"
                    title={action.summary || action.description}
                  >
                    <IconMcp size={16} />
                    {action.name}
                  </Box>
                ))}
              </Box>
            </Box>
          )}

          <ActionSecrets actionPackage={actionPackage} />
        </Box>
      </Box>
    </Container>
  );
};
