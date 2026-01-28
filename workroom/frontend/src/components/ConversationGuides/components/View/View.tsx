import { DragEvent, FC, useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { Box, Button, Typography, Menu, Divider, Progress } from '@sema4ai/components';
import {
  IconPlus,
  IconDotsHorizontal,
  IconEdit,
  IconTrash,
  IconMenu,
  IconNumberedList,
  IconCheckmark,
} from '@sema4ai/icons';
import { useAgentOAuthStateQuery, useAgentQuery } from '~/queries/agents';
import { useUpdateAgentQuestionGroupsMutation } from '~/queries/conversationGuides';

import { useMessageStream } from '../../../../hooks';
import { ConversationGuideCard } from '../ConversationGuideCard/ConversationGuideCard';
import { UpsertSectionDialog, UpsertSectionFormData } from '../UpsertSectionDialog/UpsertSectionDialog';

export interface ConversationGuidesViewProps {
  agentId: string;
  editMode: 'readOnly'; // Add write mode once ready to implement in Studio: the UI logic is there, the API will require using dedicated handlers as Studio currently uses the file system for syncing: direct agent calls should not be done.
}

export const ConversationGuidesView: FC<ConversationGuidesViewProps> = ({ agentId, editMode }) => {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [isReorderMode, setIsReorderMode] = useState(false);
  const [draggedSectionIndex, setDraggedSectionIndex] = useState<number | null>(null);

  const { threadId = '' } = useParams({ strict: false });

  const allowEditing = editMode !== 'readOnly';

  const { data: agent, isLoading: isLoadingAgent } = useAgentQuery({
    agentId,
  });
  const { mutate: updateAgentQuestionGroups, isPending: isUpdating } = useUpdateAgentQuestionGroupsMutation({});
  const { sendMessage, isStreaming, uploadingFiles } = useMessageStream({ agentId, threadId });

  const { data: oAuthState = [] } = useAgentOAuthStateQuery({ agentId });
  const requiresOAuth = oAuthState.some((state) => !state.isAuthorized);

  const canSendMessage = !requiresOAuth && !isStreaming && !uploadingFiles;

  const handleOpenUpsertSectionDialog = () => {
    setEditingIndex(null);
    setDialogOpen(true);
  };

  const handleEditSection = (index: number) => {
    setEditingIndex(index);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingIndex(null);
  };

  const handleSubmitSection = async (data: UpsertSectionFormData) => {
    const currentQuestionGroups = agent?.question_groups ?? [];
    let updatedQuestionGroups;

    if (editingIndex !== null) {
      updatedQuestionGroups = [...currentQuestionGroups];
      updatedQuestionGroups[editingIndex] = {
        title: data.name,
        questions: data.prompts.map((p) => p.text),
      };
    } else {
      updatedQuestionGroups = [
        ...currentQuestionGroups,
        {
          title: data.name,
          questions: data.prompts.map((p) => p.text),
        },
      ];
    }

    updateAgentQuestionGroups({
      agentId,
      body: {
        question_groups: updatedQuestionGroups,
      },
    });

    handleCloseDialog();
  };

  const handleDeleteSection = (index: number) => {
    const currentQuestionGroups = agent?.question_groups ?? [];
    const updatedQuestionGroups = currentQuestionGroups.filter((_, i) => i !== index);

    updateAgentQuestionGroups({
      agentId,
      body: {
        question_groups: updatedQuestionGroups,
      },
    });
  };

  const handleToggleReorderMode = () => {
    setIsReorderMode(!isReorderMode);
    setDraggedSectionIndex(null);
  };

  const handleSectionDragStart = (e: React.DragEvent, index: number) => {
    setDraggedSectionIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleSectionDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleSectionDrop = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();

    if (draggedSectionIndex === null || draggedSectionIndex === targetIndex) {
      setDraggedSectionIndex(null);
      return;
    }

    const currentQuestionGroups = [...(agent?.question_groups ?? [])];
    const [draggedSection] = currentQuestionGroups.splice(draggedSectionIndex, 1);
    currentQuestionGroups.splice(targetIndex, 0, draggedSection);

    updateAgentQuestionGroups({
      agentId,
      body: {
        question_groups: currentQuestionGroups,
      },
    });

    setDraggedSectionIndex(null);
  };

  const handleSectionDragEnd = () => {
    setDraggedSectionIndex(null);
  };

  const getInitialValues = () => {
    if (editingIndex !== null && agent?.question_groups?.[editingIndex]) {
      const section = agent.question_groups[editingIndex];
      return {
        name: section.title,
        prompts: section.questions?.map((q) => ({ text: q })) || [{ text: '' }],
      };
    }
    return {
      name: '',
      prompts: [{ text: '' }],
    };
  };

  const questionGroups = agent?.question_groups ?? [];

  if (isLoadingAgent) {
    return (
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%">
        <Box display="flex" alignItems="center" justifyContent="center" flex="1">
          <Progress />
        </Box>
      </Box>
    );
  }

  return (
    <>
      <Box display="flex" flexDirection="column" gap="$16" padding="$16" height="100%" overflow="hidden">
        {/* Header */}
        <Box display="flex" flexDirection="column" gap="$8" flexShrink="0">
          <Box display="flex" alignItems="center" gap="$8">
            <Typography variant="display-small">Conversation Guide</Typography>
          </Box>
          <Typography variant="body-medium">
            Creating a Conversation Guide helps users understand an Agent’s unique capabilities. Edit the automatically
            generated guide based on your Agent below.
          </Typography>
          {allowEditing && (
            <Box display="flex" justifyContent="space-between" paddingTop="$8" mb="$8" gap="$8">
              <Button variant="outline" round onClick={handleOpenUpsertSectionDialog} disabled={isReorderMode}>
                <IconPlus size="16" />
                Add New Section
              </Button>
              <Button
                variant={isReorderMode ? 'primary' : 'ghost'}
                round
                onClick={handleToggleReorderMode}
                disabled={questionGroups.length === 0}
                icon={isReorderMode ? IconCheckmark : IconNumberedList}
              >
                {isReorderMode ? 'Done' : 'Reorder'}
              </Button>
            </Box>
          )}
          <Divider />
        </Box>

        <Box display="flex" flexDirection="column" gap="$12" flex="1" overflow="auto" minHeight="0">
          {questionGroups.map((questionGroup, groupIndex) => (
            <Box
              draggable={isReorderMode}
              onDragStart={isReorderMode ? (e: DragEvent) => handleSectionDragStart(e, groupIndex) : undefined}
              onDragOver={isReorderMode ? handleSectionDragOver : undefined}
              onDrop={isReorderMode ? (e: DragEvent) => handleSectionDrop(e, groupIndex) : undefined}
              onDragEnd={isReorderMode ? handleSectionDragEnd : undefined}
              style={{
                opacity: draggedSectionIndex === groupIndex ? 0.5 : 1,
                cursor: isReorderMode ? 'grab' : 'default',
              }}
            >
              <Box
                display="flex"
                alignItems="center"
                justifyContent="space-between"
                marginBottom="$8"
                padding="$8"
                borderRadius="$8"
              >
                <Box display="flex" alignItems="center" gap="$8">
                  {isReorderMode && (
                    <Box display="flex" alignItems="center" justifyContent="center" style={{ cursor: 'grab' }}>
                      <IconMenu size={20} />
                    </Box>
                  )}
                  <Typography variant="display-small">{questionGroup.title}</Typography>
                </Box>
                {!isReorderMode && allowEditing && (
                  <Menu
                    trigger={
                      <Button
                        variant="ghost"
                        icon={IconDotsHorizontal}
                        round
                        aria-label="Section actions"
                        disabled={isUpdating}
                      />
                    }
                  >
                    <Menu.Item onClick={() => handleEditSection(groupIndex)} icon={IconEdit}>
                      Edit
                    </Menu.Item>
                    <Menu.Item onClick={() => handleDeleteSection(groupIndex)} icon={IconTrash}>
                      Delete
                    </Menu.Item>
                  </Menu>
                )}
              </Box>
              <Box display="flex" flexDirection="column" gap="$8">
                {questionGroup.questions?.map((question) => (
                  <ConversationGuideCard
                    title={question}
                    onClick={() => sendMessage({ text: question }, [])}
                    disabled={!canSendMessage}
                  />
                ))}
              </Box>
            </Box>
          ))}
        </Box>
      </Box>
      <UpsertSectionDialog
        open={dialogOpen}
        onClose={handleCloseDialog}
        onSubmit={handleSubmitSection}
        isLoading={isUpdating}
        initialValues={getInitialValues()}
        isEditing={editingIndex !== null}
      />
    </>
  );
};
