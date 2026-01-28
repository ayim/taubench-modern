import { type ComponentProps } from 'react';
import { Badge, Box, Card, Typography } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

/* ---------- Types ---------- */

type PlanStatus = 'pending' | 'in_progress' | 'blocked' | 'completed' | 'skipped' | string;

type PlanStepNote = {
  timestamp?: string;
  note?: string;
  level?: string;
};

type PlanStepMetadata = {
  step_id?: string;
  title?: string;
  description?: string;
  success_criteria?: string;
  dependencies?: string[];
  status?: PlanStatus;
  notes?: PlanStepNote[];
  last_updated?: string;
};

type PlanMetadata = {
  summary?: string;
  assumptions?: string;
  steps?: PlanStepMetadata[];
  last_updated?: string;
};

type MonitorEntry = {
  timestamp?: string;
  message?: string;
  level?: string;
  related_steps?: string[];
};

type MonitorMetadata = {
  latest?: MonitorEntry | null;
};

type ExecutionMetadata = {
  phase?: string;
  caption?: string;
  changed_at?: string;
  active_step_id?: string;
  active_step_title?: string;
  active_step_status?: string;
  last_step_resolution?: {
    status?: string;
    note?: string;
    level?: string;
    timestamp?: string;
  } | null;
};

export type PlanComponentMetadata = {
  plan?: PlanMetadata | null;
  monitor?: MonitorMetadata | null;
  execution?: ExecutionMetadata | null;
};

type PlanComponentProps = {
  metadata: PlanComponentMetadata;
};

/* ---------- Constants & helpers ---------- */

type StatusTone = 'subtle' | 'info' | 'success' | 'warning' | 'danger';

const DISPLAY_STEP_LIMIT = 8;

const PLAN_STATUS_CONFIG: Record<
  string,
  {
    label: string;
    badgeVariant: ComponentProps<typeof Badge>['variant'];
  }
> = {
  pending: { label: 'Pending', badgeVariant: 'secondary' },
  in_progress: { label: 'In Progress', badgeVariant: 'info' },
  blocked: { label: 'Blocked', badgeVariant: 'danger' },
  completed: { label: 'Completed', badgeVariant: 'success' },
  skipped: { label: 'Skipped', badgeVariant: 'warning' },
};

const toneToBadgeVariant = (tone: StatusTone): ComponentProps<typeof Badge>['variant'] => {
  switch (tone) {
    case 'success':
      return 'success';
    case 'danger':
      return 'danger';
    case 'warning':
      return 'warning';
    case 'info':
      return 'info';
    default:
      return 'secondary';
  }
};

const toneForPhase = (phase?: string | null): StatusTone => {
  switch (phase) {
    case 'triage':
      return 'warning';
    case 'planning':
    case 'executing-step':
    case 'monitoring':
      return 'info';
    case 'finalizing':
    case 'done':
      return 'success';
    case 'blocked':
      return 'danger';
    default:
      return 'subtle';
  }
};

const toneForNoteLevel = (level?: string | null): StatusTone => {
  switch (level) {
    case 'critical':
      return 'danger';
    case 'warning':
      return 'warning';
    case 'success':
      return 'success';
    case 'info':
      return 'info';
    default:
      return 'info';
  }
};

const formatTimestamp = (timestamp?: string) => {
  if (!timestamp) return undefined;

  const instant = new Date(timestamp);
  if (Number.isNaN(instant.getTime())) {
    return timestamp;
  }

  return instant.toLocaleString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const latestNoteForStep = (notes?: PlanStepNote[]) => {
  if (!notes || notes.length === 0) return undefined;
  return notes[notes.length - 1];
};

const formatTokenizedLabel = (value: string, separator: RegExp) =>
  value
    .split(separator)
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(' ');

const formatPhaseLabel = (phase: string) => (phase ? formatTokenizedLabel(phase, /-/g) : 'Unknown');

const formatStatusLabel = (status: string) => formatTokenizedLabel(status, /_/g);

const getPlanStatusConfig = (status?: PlanStatus) => {
  if (!status) {
    return PLAN_STATUS_CONFIG.pending;
  }

  return (
    PLAN_STATUS_CONFIG[status] ?? {
      label: formatStatusLabel(status),
      badgeVariant: 'secondary',
    }
  );
};

/* ---------- Styled components ---------- */

const Container = styled(Box)`
  margin-top: ${({ theme }) => theme.space.$12};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$16};
`;

const TimelineList = styled('ol')`
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$10};
`;

const TimelineItem = styled('li')`
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: ${({ theme }) => theme.space.$8};
  align-items: stretch;
`;

const MarkerColumn = styled(Box)`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${({ theme }) => theme.space.$4};
  padding-top: ${({ theme }) => theme.space.$2};
`;

const StepMarker = styled('span')<{ $active?: boolean }>`
  width: 14px;
  height: 14px;
  border-radius: 999px;
  border: 2px solid
    ${({ theme, $active }) => ($active ? theme.colors.border.primary.color : theme.colors.border.subtle.color)};
  background: ${({ theme, $active }) =>
    $active ? theme.colors.border.primary.color : theme.colors.background.panels.color};
  display: inline-block;
  transition: ${({ theme }) => theme.transition.normal};
`;

const StepConnector = styled('span')<{ $hidden?: boolean }>`
  width: 2px;
  flex: 1;
  display: block;
  background: ${({ theme }) => theme.colors.border.subtle.color};
  opacity: ${({ $hidden }) => ($hidden ? 0 : 1)};
  border-radius: ${({ theme }) => theme.radii.$2};
`;

const StepSurface = styled(Box)`
  border-radius: ${({ theme }) => theme.radii.$16};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  background: ${({ theme }) => theme.colors.background.panels.color};
  padding: ${({ theme }) => theme.space.$8};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.space.$4};
  box-shadow: ${({ theme }) => theme.shadows.small};
`;

const TimestampText = styled(Typography)`
  white-space: nowrap;
`;

const NoteBox = styled(Box)<{ $tone: StatusTone }>`
  padding: ${({ theme }) => `${theme.space.$4} ${theme.space.$6}`};
  border-radius: ${({ theme }) => theme.radii.$12};
  background: ${({ theme }) => theme.colors.background.subtle.color};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-left: 3px solid
    ${({ theme, $tone }) => {
      switch ($tone) {
        case 'danger':
          return theme.colors.border.error.color;
        case 'warning':
          return theme.colors.border.notification.color;
        case 'success':
          return theme.colors.border.success.color;
        case 'info':
        case 'subtle':
        default:
          return theme.colors.border.primary.color;
      }
    }};
`;

/* ---------- Small presentational pieces ---------- */

type PlanHeaderProps = {
  phaseLabel?: string;
  phaseBadgeVariant?: ComponentProps<typeof Badge>['variant'];
  showPhasePill: boolean;
  planTimestamp?: string;
};

const PlanHeader = ({ phaseLabel, phaseBadgeVariant, showPhasePill, planTimestamp }: PlanHeaderProps) => (
  <Box display="flex" flexWrap="wrap" alignItems="center" flex="1 1 0" gap="$3">
    <Typography variant="body-medium" fontWeight="600">
      Plan
    </Typography>

    <Box display="flex" alignItems="center" gap="$3" style={{ marginLeft: 'auto' }}>
      {showPhasePill && phaseLabel && phaseBadgeVariant && (
        <Badge size="small" variant={phaseBadgeVariant} style={{ marginRight: '4px' }} label={phaseLabel} />
      )}

      {planTimestamp && (
        <TimestampText variant="body-small" color="content.subtle">
          Updated {planTimestamp}
        </TimestampText>
      )}
    </Box>
  </Box>
);

type MonitorNoteProps = {
  entry?: MonitorEntry | null;
};

const MonitorNote = ({ entry }: MonitorNoteProps) => {
  if (!entry?.message) return null;

  return (
    <NoteBox $tone={toneForNoteLevel(entry.level)}>
      <Typography variant="body-small" color="content.primary">
        {entry.message}
      </Typography>
    </NoteBox>
  );
};

/* ---------- Step timeline ---------- */

type StepTimelineProps = {
  steps: PlanStepMetadata[];
  activeStepId: string | null;
};

type StepTimelineItemProps = {
  step: PlanStepMetadata;
  index: number;
  isLast: boolean;
  isActive: boolean;
};

const StepTimelineItem = ({ step, index, isLast, isActive }: StepTimelineItemProps) => {
  const note = latestNoteForStep(step.notes);
  const statusConfig = getPlanStatusConfig(step.status);
  const stepLabel = step.title || step.step_id || `Step ${index + 1}`;
  const dependencies = step.dependencies?.filter(Boolean) ?? [];
  const stepTimestamp = formatTimestamp(note?.timestamp ?? step.last_updated);

  return (
    <TimelineItem>
      <MarkerColumn>
        <StepMarker $active={isActive} />
        <StepConnector $hidden={isLast} />
      </MarkerColumn>
      <StepSurface>
        <Box display="flex" flexDirection="column" gap="$2">
          <Box display="flex" flexWrap="wrap" alignItems="center" justifyContent="space-between" gap="$3">
            <Box display="flex" alignItems="center" gap="$3" flex="1 1 0" minWidth="0">
              <Typography variant="body-medium" fontWeight="600">
                {stepLabel}
              </Typography>
              <Badge
                size="small"
                style={{ marginLeft: 'auto', marginRight: '8px' }}
                variant={statusConfig.badgeVariant}
                label={statusConfig.label}
              />
            </Box>
            {stepTimestamp && (
              <TimestampText variant="body-small" color="content.subtle">
                {stepTimestamp}
              </TimestampText>
            )}
          </Box>

          {step.description && (
            <Typography variant="body-small" color="content.subtle">
              {step.description}
            </Typography>
          )}
        </Box>

        {step.success_criteria && (
          <Typography variant="body-small" color="content.subtle">
            Success criteria: {step.success_criteria}
          </Typography>
        )}

        {dependencies.length > 0 && (
          <Typography variant="body-small" color="content.subtle">
            Depends on: {dependencies.join(', ')}
          </Typography>
        )}

        {note?.note && (
          <NoteBox $tone={toneForNoteLevel(note.level)}>
            <Typography variant="body-small" color="content.primary">
              {note.note}
            </Typography>
          </NoteBox>
        )}
      </StepSurface>
    </TimelineItem>
  );
};

const StepTimeline = ({ steps, activeStepId }: StepTimelineProps) => {
  if (!steps.length) return null;

  return (
    <TimelineList>
      {steps.map((step, index) => (
        <StepTimelineItem
          key={step.step_id ?? `${step.title ?? 'step'}-${index}`}
          step={step}
          index={index}
          isLast={index === steps.length - 1}
          isActive={Boolean(activeStepId && activeStepId === step.step_id)}
        />
      ))}
    </TimelineList>
  );
};

/* ---------- Main component ---------- */

const PlanViewerComponent = ({ metadata }: PlanComponentProps) => {
  const { plan, monitor, execution } = metadata;

  const steps = plan?.steps ?? [];
  const totalPlanSteps = steps.length;
  const stepsToDisplay = steps.slice(0, DISPLAY_STEP_LIMIT);
  const hasAdditionalSteps = totalPlanSteps > DISPLAY_STEP_LIMIT;
  const completedSteps = steps.filter((step) => step.status === 'completed').length;

  const planSummaryText = plan?.summary?.trim();
  const hasPlanSummary = Boolean(planSummaryText);
  const hasPlanSteps = totalPlanSteps > 0;
  const planRecorded = hasPlanSummary || hasPlanSteps;

  const currentPhase = execution?.phase;
  const currentPhaseCaption = execution?.caption;
  const phaseChangedAt = execution?.changed_at;

  const displayPhase = currentPhase || (planRecorded ? 'executing-step' : undefined);
  const phaseLabel = displayPhase ? formatPhaseLabel(displayPhase) : undefined;
  const phaseTone = toneForPhase(displayPhase);
  const phaseBadgeVariant = toneToBadgeVariant(phaseTone);

  const hasPhaseCaption = Boolean(currentPhaseCaption);
  const hasPhaseTimestamp = Boolean(phaseChangedAt);
  const showPhasePill = Boolean(displayPhase);
  const hasPhaseInfo = showPhasePill || hasPhaseCaption || hasPhaseTimestamp;

  let stepsDescription = 'Plan not available';
  if (hasPlanSteps) {
    stepsDescription = `${completedSteps} of ${totalPlanSteps} completed`;
  } else if (planRecorded) {
    stepsDescription = 'No procedural steps logged yet';
  }

  const planTimestamp = plan?.last_updated ? formatTimestamp(plan.last_updated) : undefined;
  const latestMonitorEntry = monitor?.latest ?? undefined;

  // If we truly have nothing meaningful to show, bail out.
  if (!planRecorded && !hasPhaseInfo && !latestMonitorEntry?.message) {
    return null;
  }

  const activeStepId = execution?.active_step_id ?? null;

  return (
    <Container role="region" aria-label="Agent plan and monitor summary">
      <Card title="">
        <Box display="flex" flexDirection="column" gap="$6">
          <PlanHeader
            phaseLabel={phaseLabel}
            phaseBadgeVariant={phaseBadgeVariant}
            showPhasePill={Boolean(hasPhaseInfo && displayPhase)}
            planTimestamp={planTimestamp}
          />

          {planRecorded ? (
            <Typography variant="body-medium" color="content.primary">
              {planSummaryText || 'Plan metadata recorded. Waiting for the agent to add a written summary.'}
            </Typography>
          ) : (
            <Typography variant="body-medium" color="content.subtle">
              No plan is currently recorded. The agent will create one during the next planning pass.
            </Typography>
          )}

          <MonitorNote entry={latestMonitorEntry} />

          <Typography variant="body-small" color="content.subtle">
            {stepsDescription}
          </Typography>

          {stepsToDisplay.length > 0 ? (
            <>
              <StepTimeline steps={stepsToDisplay} activeStepId={activeStepId} />
              {hasAdditionalSteps && (
                <Typography variant="body-small" color="content.subtle">
                  Showing the first {DISPLAY_STEP_LIMIT} steps. Refer to the full metadata for the remaining steps.
                </Typography>
              )}
            </>
          ) : (
            <Typography variant="body-small" color="content.subtle">
              {planRecorded
                ? 'No procedural steps have been registered yet. The agent may still be extracting them from the Runbook.'
                : 'Steps will appear once the agent has written the initial plan.'}
            </Typography>
          )}
        </Box>
      </Card>
    </Container>
  );
};

export const PlanViewer = PlanViewerComponent;
