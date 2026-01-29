/* eslint-disable no-restricted-syntax */
/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck

import { useCallback, useEffect, useState } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $getRoot, $isElementNode, LexicalNode } from 'lexical';
import { Badge, Box, Button, Divider } from '@sema4ai/components';
import { IconCheck, IconClose, IconArrowUp, IconArrowDown } from '@sema4ai/icons';
import { $isSuggestionNode, SuggestionNode } from './nodes/SuggestionNode';

export const SuggestionActionsPlugin = () => {
  const [editor] = useLexicalComposerContext();
  const [suggestionNodes, setSuggestionNodes] = useState<SuggestionNode[]>([]);
  const [currentSuggestionIndex, setCurrentSuggestionIndex] = useState<number>(0);

  // Track suggestion nodes in the editor
  useEffect(() => {
    const updateSuggestions = () => {
      editor.getEditorState().read(() => {
        const root = $getRoot();

        // Recursively find all suggestion nodes in the tree
        const findSuggestionNodes = (node: LexicalNode | null | undefined): SuggestionNode[] => {
          if (!node) {
            return [];
          }

          const suggestions: SuggestionNode[] = [];

          if ($isSuggestionNode(node)) {
            suggestions.push(node);
          }

          // Check children if this is an element node
          if ($isElementNode(node)) {
            const children = node.getChildren();
            for (const child of children) {
              suggestions.push(...findSuggestionNodes(child));
            }
          }

          return suggestions;
        };

        const suggestions = findSuggestionNodes(root);
        setSuggestionNodes(suggestions);
      });
    };

    // Initial check
    updateSuggestions();

    // Listen for editor updates
    return editor.registerUpdateListener(() => {
      updateSuggestions();
    });
  }, [editor]);

  // Reset current index when suggestions change
  useEffect(() => {
    if (suggestionNodes.length > 0 && currentSuggestionIndex >= suggestionNodes.length) {
      setCurrentSuggestionIndex(0);
    }
  }, [suggestionNodes, currentSuggestionIndex]);

  const handleKeepAll = useCallback(() => {
    // Accept all suggestions
    // Note: acceptSuggestion already calls editor.update() internally
    suggestionNodes.forEach((node) => {
      node.acceptSuggestion(editor);
    });
  }, [editor, suggestionNodes]);

  const handleRejectAll = useCallback(() => {
    // Reject all suggestions
    // Note: rejectSuggestion already calls editor.update() internally
    suggestionNodes.forEach((node) => {
      node.rejectSuggestion(editor);
    });
  }, [editor, suggestionNodes]);

  const scrollToSuggestion = useCallback(
    (index: number) => {
      if (index < 0 || index >= suggestionNodes.length) {
        return;
      }

      editor.getEditorState().read(() => {
        const node = suggestionNodes[index];
        const key = node.getKey();
        const domElement = editor.getElementByKey(key);

        if (domElement) {
          domElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
            inline: 'nearest',
          });
        }
      });
    },
    [editor, suggestionNodes],
  );

  const handleNavigatePrevious = useCallback(() => {
    const newIndex = currentSuggestionIndex > 0 ? currentSuggestionIndex - 1 : suggestionNodes.length - 1;

    setCurrentSuggestionIndex(newIndex);
    scrollToSuggestion(newIndex);
  }, [currentSuggestionIndex, suggestionNodes.length, scrollToSuggestion]);

  const handleNavigateNext = useCallback(() => {
    const newIndex = currentSuggestionIndex < suggestionNodes.length - 1 ? currentSuggestionIndex + 1 : 0;

    setCurrentSuggestionIndex(newIndex);
    scrollToSuggestion(newIndex);
  }, [currentSuggestionIndex, suggestionNodes.length, scrollToSuggestion]);

  // Don't render if no suggestions
  if (suggestionNodes.length === 0) {
    return null;
  }

  return (
    <Box
      display="flex"
      flexDirection="row"
      alignItems="center"
      justifyContent="center"
      gap={8}
      padding={16}
      style={{
        position: 'sticky',
        bottom: 32,
        zIndex: 9999,
      }}
    >
      <Box
        display="flex"
        flexDirection="row"
        alignItems="center"
        gap={8}
        backgroundColor="background.panels"
        borderRadius={32}
        padding={8}
        borderColor="border.primary"
      >
        <Badge
          aria-label="Keep all changes"
          forwardedAs="button"
          icon={IconCheck}
          iconVisible
          iconColor="content.success"
          variant="success"
          onClick={handleKeepAll}
          label="Keep All"
        />
        <Badge
          aria-label="Reject all changes"
          forwardedAs="button"
          icon={IconClose}
          iconVisible
          iconColor="content.error"
          variant="danger"
          onClick={handleRejectAll}
          label="Reject All"
        />
        <Divider orientation="vertical" />
        <Button
          aria-label="Navigate to previous suggestion"
          icon={IconArrowUp}
          onClick={handleNavigatePrevious}
          round
          size="small"
          variant="outline"
        />
        <Button
          aria-label="Navigate to next suggestion"
          icon={IconArrowDown}
          onClick={handleNavigateNext}
          round
          size="small"
          variant="outline"
        />
      </Box>
    </Box>
  );
};
