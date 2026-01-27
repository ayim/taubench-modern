/* eslint-disable @typescript-eslint/no-shadow */
import { FC, useEffect, useCallback, useRef, useState } from 'react';
import {
  COMMAND_PRIORITY_EDITOR,
  createCommand,
  LexicalCommand,
  LexicalEditor,
  $getRoot,
  TextNode,
  $createTextNode,
  $isTextNode,
  RootNode,
  LexicalNode,
  $isElementNode,
  TextModeType,
} from 'lexical';
import { Box, Button, Divider, Input, Popover, PopoverTriggerProps, Tooltip, Typography } from '@sema4ai/components';
import {
  IconArrowDown,
  IconArrowUp,
  IconChevronDown,
  IconChevronUp,
  IconMatchWholeWord,
  IconMatchWordCase,
  IconReplaceAll,
  IconReplaceCurrent,
  IconSearch,
} from '@sema4ai/icons';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $createHighlightNode,
  $isHighlightNode,
  CURRENT_MATCH_COLOR,
  HighlightNode,
  MATCH_COLOR,
} from './HighlightNode';

const FIND_COMMAND: LexicalCommand<{ searchValue: string; isMatchWholeWord: boolean; isMatchWordCase: boolean }> =
  createCommand('FIND_COMMAND');

type NodeInfo = {
  format: number;
  style: string;
  mode: TextModeType;
  details: number;
};

type MatchedText = {
  nodes: HighlightNode[];
};

const getTextNodeInfo = (node: TextNode): NodeInfo => {
  return {
    format: node.getFormat(),
    style: node.getStyle(),
    mode: node.getMode(),
    details: node.getDetail(),
  };
};

const setTextNodeInfo = (node: TextNode, info: NodeInfo) => {
  node.setFormat(info.format);
  node.setStyle(info.style);
  node.setMode(info.mode);
  node.setDetail(info.details);
};

// Remove all highlight nodes recursively
const removeHighlights = (node: LexicalNode) => {
  if ($isHighlightNode(node)) {
    const nodeInfo = getTextNodeInfo(node);
    const textNode = $createTextNode(node.getTextContent());
    setTextNodeInfo(textNode, nodeInfo);
    node.replace(textNode);
  } else if ($isElementNode(node)) {
    node.getChildren().forEach(removeHighlights);
  }
};

const findMatchesInText = (
  text: string,
  searchTerm: string,
  isMatchWholeWord: boolean,
  isMatchWordCase: boolean,
): number[] => {
  const matches: number[] = [];

  // Prepare text and search term based on case sensitivity
  const searchText = isMatchWordCase ? text : text.toLowerCase();
  const searchPattern = isMatchWordCase ? searchTerm : searchTerm.toLowerCase();

  let index = 0;
  let foundIndex = searchText.indexOf(searchPattern, index);

  while (foundIndex !== -1) {
    // Check if we need to match whole words
    if (isMatchWholeWord) {
      const charBefore = foundIndex > 0 ? text[foundIndex - 1] : '';
      const charAfter = foundIndex + searchTerm.length < text.length ? text[foundIndex + searchTerm.length] : '';

      // Check if both boundaries are word boundaries
      const isWordBoundaryBefore = foundIndex === 0 || !/\w/.test(charBefore);
      const isWordBoundaryAfter = foundIndex + searchTerm.length === text.length || !/\w/.test(charAfter);

      if (isWordBoundaryBefore && isWordBoundaryAfter) {
        matches.push(foundIndex);
      }
    } else {
      matches.push(foundIndex);
    }

    index = foundIndex + searchTerm.length;
    foundIndex = searchText.indexOf(searchPattern, index);
  }

  return matches;
};

// Helper function to get all text nodes in the same line
const getLineTextNodes = (node: TextNode): TextNode[] => {
  const lineNodes: TextNode[] = [node];
  let current = node;

  // Get nodes after the current ones only
  current = node;
  while (
    current.getNextSibling() &&
    !$isHighlightNode(current.getNextSibling() as LexicalNode) &&
    $isTextNode(current.getNextSibling())
  ) {
    current = current.getNextSibling() as TextNode;
    lineNodes.push(current);
  }

  return lineNodes;
};

export const SearchAndReplacePlugin: FC = () => {
  const [editor] = useLexicalComposerContext();
  const [searchValue, setSearchValue] = useState<string>('');
  const [replaceValue, setReplaceValue] = useState<string>('');
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState<MatchedText[]>([]);
  const [currentMatch, setCurrentMatch] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const [isMatchWordCase, setIsMatchWordCase] = useState(false);
  const [isMatchWholeWord, setIsMatchWholeWord] = useState(false);

  const [showReplaceInput, setShowReplaceInput] = useState(false);

  const findCommandListener = useCallback(
    (
      {
        searchValue,
        isMatchWholeWord,
        isMatchWordCase,
      }: { searchValue: string; isMatchWholeWord: boolean; isMatchWordCase: boolean },
      editor: LexicalEditor,
    ): boolean => {
      // Use createTextNode to create a new text node with the same content and formatting.
      // TODO: just edit the node instead of replacing it so nothing would be lost accidentally.
      // The problem is that the node cannot easily be highligted partially, there is only
      // set background color for the whole node.

      setHighlightedNodes([]);

      if (!searchValue) {
        // If search is empty, just clear highlights
        editor.update(() => {
          const root = $getRoot();
          removeHighlights(root);
        });
        return true;
      }

      editor.update(() => {
        const root = $getRoot();
        const processedNodes = new Set<string>();
        const nodesToHighlight: MatchedText[] = [];

        // First, remove any existing highlights using the same recursive function
        removeHighlights(root);

        // Find and highlight all matches
        const processTextNode = (node: TextNode) => {
          // Skip if this node has already been processed (it was part of a previous line)
          if (processedNodes.has(node.getKey())) return;

          const lineNodes = getLineTextNodes(node);

          // Skip if any node in this line has been processed
          if (lineNodes.some((n) => processedNodes.has(n.getKey()))) return;

          const fullText = lineNodes.map((n) => n.getTextContent()).join('');
          const matches = findMatchesInText(fullText, searchValue, isMatchWholeWord, isMatchWordCase);

          if (matches.length > 0) {
            // Process each text node based on the matches
            let currentPosition = 0;

            const matchNodes: MatchedText[] = [];

            lineNodes.forEach((currentNode) => {
              processedNodes.add(currentNode.getKey());
              const nodeText = currentNode.getTextContent();
              const nodeStart = currentPosition;
              const nodeEnd = currentPosition + nodeText.length;

              // Find matches that overlap with this node
              const nodeMatches = matches.filter(
                (match) =>
                  (match >= nodeStart && match < nodeEnd) || // match starts in this node
                  (match < nodeStart && match + searchValue.length > nodeStart), // match overlaps from previous node
              );

              if (nodeMatches.length > 0) {
                let lastIndex = 0;
                const nodes = [];
                const nodeInfo = getTextNodeInfo(currentNode);

                nodeMatches.forEach((match) => {
                  const matchStartInNode = Math.max(0, match - nodeStart);
                  const matchEndInNode = Math.min(nodeText.length, match + searchValue.length - nodeStart);

                  // Add text before match
                  if (matchStartInNode > lastIndex) {
                    const textNode = $createTextNode(nodeText.slice(lastIndex, matchStartInNode));
                    setTextNodeInfo(textNode, nodeInfo);
                    nodes.push(textNode);
                  }

                  // Add highlighted match
                  const highlightNode = $createHighlightNode(nodeText.slice(matchStartInNode, matchEndInNode));
                  setTextNodeInfo(highlightNode, nodeInfo);
                  nodes.push(highlightNode);
                  lastIndex = matchEndInNode;

                  // Add new MatchedText object for each match and also include all nodes connected to the match
                  if (match >= nodeStart) {
                    matchNodes.push({ nodes: [highlightNode] });
                  } else if (matchNodes.length > 0) {
                    matchNodes[matchNodes.length - 1]?.nodes.push(highlightNode);
                  }
                });

                // Add remaining text
                if (lastIndex < nodeText.length) {
                  const textNode = $createTextNode(nodeText.slice(lastIndex));
                  setTextNodeInfo(textNode, nodeInfo);
                  nodes.push(textNode);
                }

                const parent = currentNode.getParent();
                if (parent) {
                  nodes.forEach((newNode) => {
                    currentNode.insertBefore(newNode);
                  });
                  currentNode.remove();
                }
              } else {
                // Mark all nodes in this line as processed even if no matches
                lineNodes.forEach((n) => processedNodes.add(n.getKey()));
              }

              currentPosition += nodeText.length;
            });

            if (matchNodes.length > 0) {
              nodesToHighlight.push(...matchNodes);
            }
          }
        };

        // Traverse all nodes recursively and process text nodes
        const traverseNodes = (node: RootNode | LexicalNode) => {
          if ($isTextNode(node)) {
            processTextNode(node);
            return;
          }

          if ($isElementNode(node)) {
            const children = node.getChildren();
            children.forEach((c) => traverseNodes(c));
          }
        };

        traverseNodes(root);

        setHighlightedNodes(nodesToHighlight);
      });

      return true;
    },
    [],
  );

  useEffect(() => {
    const currentIndex = currentMatch - 1;

    if (highlightedNodes.length > currentIndex) {
      const node = highlightedNodes[currentIndex];
      // scroll to position
      const domElement = editor.getElementByKey(node?.nodes[0].getKey());
      domElement?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // highlight the node to orange
      node?.nodes.forEach((n): void => {
        n.setBackgroundColor(editor, n.getKey(), CURRENT_MATCH_COLOR);
      });
    }

    return (): void => {
      if (highlightedNodes.length > currentIndex) {
        const node = highlightedNodes[currentIndex];
        node?.nodes.forEach((n) => {
          n.setBackgroundColor(editor, n.getKey(), MATCH_COLOR);
        });
      }
    };
  }, [currentMatch, highlightedNodes]);

  const findPrevious = () => {
    setCurrentMatch((prev) => {
      if (prev === 0) {
        return highlightedNodes.length;
      }

      const newMatch = prev - 1;
      if (newMatch < 1) {
        return highlightedNodes.length;
      }
      return newMatch;
    });
  };

  const findNext = () => {
    setCurrentMatch((prev) => {
      if (prev === 0) {
        return highlightedNodes.length === 0 ? 0 : 1;
      }

      const newMatch = prev + 1;
      if (newMatch > highlightedNodes.length) {
        return 1;
      }
      return newMatch;
    });
  };

  const replaceMatchedText = (nodes: HighlightNode[]) => {
    editor.update(() => {
      if (nodes.length > 0) {
        // Create a new text node with the replacement value
        const nodeInfo = getTextNodeInfo(nodes[0]);
        const textNode = $createTextNode(replaceValue);
        setTextNodeInfo(textNode, nodeInfo);

        // Replace the first node with the new text node
        nodes[0].replace(textNode);

        // Remove the remaining nodes
        for (let i = 1; i < nodes.length; i += 1) {
          nodes[i].remove();
        }
      }
    });
  };

  const replaceCurrentValue = useCallback(() => {
    if (highlightedNodes.length === 0 || !replaceValue) {
      return;
    }

    if (currentMatch === 0) {
      findNext();
      return;
    }

    const { nodes } = highlightedNodes[currentMatch - 1];

    replaceMatchedText(nodes);

    // Re-run the search to update highlights
    editor.dispatchCommand(FIND_COMMAND, { searchValue, isMatchWholeWord, isMatchWordCase });
  }, [highlightedNodes, currentMatch, replaceValue, searchValue, isMatchWholeWord, isMatchWordCase]);

  const replaceAllValues = useCallback(() => {
    if (highlightedNodes.length === 0 || !replaceValue) {
      return;
    }

    highlightedNodes.forEach((node) => replaceMatchedText(node.nodes));

    // Re-run the search to update highlights
    editor.dispatchCommand(FIND_COMMAND, { searchValue, isMatchWholeWord, isMatchWordCase });
  }, [highlightedNodes, replaceValue, searchValue, isMatchWholeWord, isMatchWordCase]);

  useEffect(() => {
    setCurrentMatch(0);
  }, [highlightedNodes]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for Ctrl+f (or Cmd+f on Mac)
      if ((event.ctrlKey || event.metaKey) && event.key === 'f') {
        event.preventDefault(); // Prevent default browser find
        setIsOpen(true);
        inputRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const search = (value: string) => {
    editor.update(() => {
      removeHighlights($getRoot());
    });
    editor.dispatchCommand(FIND_COMMAND, { searchValue: value, isMatchWholeWord, isMatchWordCase });
  };

  useEffect(() => {
    if (!isOpen) {
      editor.dispatchCommand(FIND_COMMAND, { searchValue: '', isMatchWholeWord, isMatchWordCase });
      setSearchValue('');
      setReplaceValue('');
    }
  }, [isOpen]);

  useEffect(() => {
    return editor.registerCommand(FIND_COMMAND, findCommandListener, COMMAND_PRIORITY_EDITOR);
  }, [editor, findCommandListener]);

  useEffect(() => {
    search(searchValue);
  }, [searchValue]);

  const trigger = useCallback(({ referenceProps, referenceRef }: PopoverTriggerProps) => {
    return (
      <Button
        ref={referenceRef}
        {...referenceProps}
        variant="ghost"
        aria-label="open-search-dialog"
        onClick={() => (isOpen ? setIsOpen(false) : setIsOpen(true))}
        icon={IconSearch}
      />
    );
  }, []);

  return (
    <Box>
      <Popover open={isOpen} placement="bottom-start" trigger={trigger}>
        <Box display="flex" flexDirection="column" alignItems="center" gap={8} width="100%">
          <Box display="flex" flexDirection="row" alignItems="center" gap={8} width="100%">
            <Tooltip text="Next match" placement="bottom">
              <Button
                disabled={highlightedNodes.length === 0}
                icon={IconArrowDown}
                label=""
                aria-label="search-down"
                size="small"
                variant="ghost"
                onClick={findNext}
              />
            </Tooltip>
            <Tooltip text="Previous match" placement="bottom">
              <Button
                disabled={highlightedNodes.length === 0}
                icon={IconArrowUp}
                label=""
                aria-label="search-up"
                size="small"
                variant="ghost"
                onClick={findPrevious}
              />
            </Tooltip>
            <Input
              variant="ghost"
              placeholder="Search"
              value={searchValue}
              label=""
              autoFocus
              onChange={(e) => setSearchValue(e.target.value)}
              ref={inputRef}
            />

            <Box display="flex" flexDirection="row" alignItems="center" gap={2} height="100%">
              <Tooltip text="Match Case" placement="top">
                <Button
                  variant={isMatchWordCase ? 'secondary' : 'ghost-subtle'}
                  aria-label=""
                  size="small"
                  icon={IconMatchWordCase}
                  onClick={() => {
                    setIsMatchWordCase(!isMatchWordCase);
                    editor.dispatchCommand(FIND_COMMAND, {
                      searchValue,
                      isMatchWholeWord,
                      isMatchWordCase: !isMatchWordCase,
                    });
                  }}
                  round
                />
              </Tooltip>
              <Tooltip text="Match Whole Word" placement="top">
                <Button
                  variant={isMatchWholeWord ? 'secondary' : 'ghost-subtle'}
                  aria-label=""
                  size="small"
                  icon={IconMatchWholeWord}
                  onClick={() => {
                    setIsMatchWholeWord(!isMatchWholeWord);
                    editor.dispatchCommand(FIND_COMMAND, {
                      searchValue,
                      isMatchWholeWord: !isMatchWholeWord,
                      isMatchWordCase,
                    });
                  }}
                  round
                />
              </Tooltip>
              <Box display="flex" flexDirection="row" alignItems="center" gap={2} p={8}>
                <Typography variant="body-small" fontWeight={600} color="content.subtle">
                  {currentMatch}/{highlightedNodes.length}
                </Typography>
              </Box>
              <Divider orientation="vertical" as="hr" color="border.subtle" />
              <Tooltip text={showReplaceInput ? 'Hide Replace' : 'Show Replace'} placement="top">
                <Button
                  icon={showReplaceInput ? IconChevronUp : IconChevronDown}
                  aria-label="show-replace-input"
                  size="small"
                  variant="ghost"
                  onClick={() => setShowReplaceInput(!showReplaceInput)}
                />
              </Tooltip>
            </Box>
          </Box>
          {showReplaceInput && (
            <Box display="flex" flexDirection="row" alignItems="center" gap={8} width="100%">
              <Tooltip text="Replace next" placement="bottom">
                <Button
                  disabled={highlightedNodes.length === 0 || !replaceValue}
                  icon={IconReplaceCurrent}
                  label=""
                  aria-label="replace"
                  size="small"
                  variant="ghost"
                  onClick={replaceCurrentValue}
                />
              </Tooltip>
              <Tooltip text="Replace all" placement="bottom">
                <Button
                  disabled={highlightedNodes.length === 0 || !replaceValue}
                  icon={IconReplaceAll}
                  label=""
                  aria-label="replace-all"
                  size="small"
                  variant="ghost"
                  onClick={replaceAllValues}
                />
              </Tooltip>
              <Input
                variant="ghost"
                placeholder="Replace"
                value={replaceValue}
                label=""
                onChange={(e) => setReplaceValue(e.target.value)}
                autoWidth
              />
            </Box>
          )}
        </Box>
      </Popover>
    </Box>
  );
};
