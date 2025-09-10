import { Color } from '@sema4ai/theme';
import { BadgeVariant } from '@sema4ai/components';
import { IconStatusCompleted, IconStatusError, IconStatusPending, IconStatusProcessing } from '@sema4ai/icons';
import { Trial } from './types';

export const getIconColor = (status: Trial['status']): Color => {
    switch (status) {
      case 'succeeded':
        return 'green80';
      case 'failed':
        return 'red80';
      case 'running':
        return 'yellow80';
      case 'pending':
      default:
        return 'red80';
    }
  };
  
  export const getBadgeColor = (status: Trial['status']): BadgeVariant => {
    switch (status) {
      case 'succeeded':
        return 'green';
      case 'failed':
        return 'red';
      case 'running':
        return 'yellow';
      case 'pending':
      default:
        return 'red';
    }
  };
  
  export const getBadgeIcon = (status: Trial['status']) => {
    switch (status) {
      case 'succeeded':
        return IconStatusCompleted;
      case 'failed':
        return IconStatusError;
      case 'running':
        return IconStatusProcessing;
      case 'pending':
        return IconStatusPending;
      default:
        return IconStatusPending;
    }
  };
  
  export const getStatusLabel = (status: Trial['status']) => {
    switch (status) {
      case 'succeeded':
        return 'Passed';
      case 'failed':
        return 'Failed';
      case 'running':
        return 'Running';
      case 'pending':
      default:
        return 'Pending';
    }
  };
  
  export const getRunStatus = (trials: Trial[]): Trial['status'] => {
    if (trials.length === 0) return 'pending';
    
    if (trials.some(trial => trial.status === 'running')) return 'running';
    
    if (trials.some(trial => trial.status === 'pending')) return 'pending';
    
    if (trials.every(trial => trial.status === 'succeeded')) return 'succeeded';
    
    return 'failed';
  };