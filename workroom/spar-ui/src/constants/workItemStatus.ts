import { BadgeVariant } from '@sema4ai/components';
import {
  IconLoading,
  IconStatusCompleted,
  IconStatusError,
  IconStatusIdle,
  IconStatusNew,
  IconStatusPending,
  IconStatusUnresolved,
  IconType,
} from '@sema4ai/icons';
import { ComponentProps } from 'react';
import { WorkItemStatus } from '../queries/workItems';

export type WorkItemStatusConfig = {
  label: string;
  variant: BadgeVariant;
  icon: IconType;
  iconColor: Extract<
    ComponentProps<IconType>['color'],
    'content.error' | 'content.subtle' | 'content.success' | 'background.success' | 'background.notification'
  >;
};

export const WORK_ITEM_STATUS_CONFIG: Record<WorkItemStatus, WorkItemStatusConfig> = {
  ERROR: {
    label: 'Failed',
    variant: 'danger',
    icon: IconStatusUnresolved,
    iconColor: 'content.error',
  },
  PENDING: {
    label: 'In Queue',
    variant: 'secondary',
    icon: IconStatusPending,
    iconColor: 'content.subtle',
  },
  EXECUTING: {
    label: 'Processing',
    variant: 'info',
    icon: IconLoading,
    iconColor: 'content.subtle',
  },
  COMPLETED: {
    label: 'Completed',
    variant: 'success',
    icon: IconStatusCompleted,
    iconColor: 'background.success',
  },
  CANCELLED: {
    label: 'Cancelled',
    variant: 'secondary',
    icon: IconStatusError,
    iconColor: 'content.error',
  },
  NEEDS_REVIEW: {
    label: 'Needs Review',
    variant: 'warning',
    icon: IconStatusIdle,
    iconColor: 'background.notification',
  },
  INDETERMINATE: {
    label: 'Indeterminate',
    variant: 'secondary',
    icon: IconStatusIdle,
    iconColor: 'background.notification',
  },
  DRAFT: {
    label: 'Draft',
    variant: 'secondary',
    icon: IconStatusPending,
    iconColor: 'content.subtle',
  },
};

export const DEFAULT_WORK_ITEM_STATUS_CONFIG: WorkItemStatusConfig = {
  label: 'Unknown',
  variant: 'secondary',
  icon: IconStatusNew,
  iconColor: 'content.subtle',
};

export const STATUS_ORDER: WorkItemStatus[] = [
  'ERROR',
  'PENDING',
  'EXECUTING',
  'COMPLETED',
  'CANCELLED',
  'NEEDS_REVIEW',
];

/**
 * All work item status values
 * Derived from WORK_ITEM_STATUS_CONFIG to maintain a single source of truth
 */
export const WORK_ITEM_STATUS_VALUES: WorkItemStatus[] = Object.keys(WORK_ITEM_STATUS_CONFIG) as WorkItemStatus[];
