import { useEffect } from 'react';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import {
  $getRoot,
  $getSelection,
  $isElementNode,
  $isRangeSelection,
  $isRootNode,
  COMMAND_PRIORITY_HIGH,
  COPY_COMMAND,
  ElementNode,
  LexicalNode,
  PASTE_COMMAND,
} from 'lexical';

import { MARKDOWN_TRANSFORMERS } from './lexical-markdown/MarkdownTransformers';
import { $convertFromMarkdownString } from './lexical-markdown';
import { createMarkdownExport } from './lexical-markdown/MarkdownExport';

/**
 * Finds the top-level node (direct child of root) for a given node.
 */
const findTopLevelNode = (node: LexicalNode): LexicalNode => {
  let topLevelNode: LexicalNode = node;
  let parent = topLevelNode.getParent();

  while (parent && parent.getKey() !== 'root') {
    topLevelNode = parent;
    parent = topLevelNode.getParent();
  }

  return topLevelNode;
};

/**
 * Checks if a range selection covers an entire top-level block or multiple blocks.
 * Returns false for partial selections within a single block.
 */
const isFullBlockSelection = (selection: ReturnType<typeof $getSelection>, selectedNodes: LexicalNode[]): boolean => {
  if (!$isRangeSelection(selection) || selectedNodes.length === 0) {
    return false;
  }

  // Find all unique top-level nodes that are selected
  const seenBlocks = new Set<string>();
  const topLevelNodes: LexicalNode[] = [];

  selectedNodes.forEach((node) => {
    const topLevelNode = findTopLevelNode(node);
    const blockKey = topLevelNode.getKey();

    if (!seenBlocks.has(blockKey)) {
      seenBlocks.add(blockKey);
      topLevelNodes.push(topLevelNode);
    }
  });

  // If multiple blocks are selected, we'll handle it
  if (topLevelNodes.length > 1) {
    return true;
  }

  // For single block, check if the entire block is selected
  if (topLevelNodes.length === 1 && $isElementNode(topLevelNodes[0])) {
    const block = topLevelNodes[0] as ElementNode;
    const blockTextContent = block.getTextContent();
    const selectedTextContent = selection.getTextContent();

    // If the selected text matches the entire block text, it's a full block selection
    // Also handle empty blocks
    if (blockTextContent === selectedTextContent || blockTextContent.length === 0) {
      return true;
    }
  }

  return false;
};

/**
 * Exports selected nodes as markdown, preserving all formatting (bold, italic, headings, lists, tables, etc.).
 * Only exports when full blocks are selected.
 */
const exportSelectedNodesAsMarkdown = (selectedNodes: LexicalNode[]): string => {
  if (selectedNodes.length === 0) {
    return '';
  }

  // Find all unique top-level nodes that are selected
  const seenBlocks = new Set<string>();
  const topLevelNodes: LexicalNode[] = [];

  selectedNodes.forEach((node) => {
    const topLevelNode = findTopLevelNode(node);
    const blockKey = topLevelNode.getKey();

    if (!seenBlocks.has(blockKey)) {
      seenBlocks.add(blockKey);
      topLevelNodes.push(topLevelNode);
    }
  });

  // Get the root node - we'll use it as a parent to export from
  const root = $getRoot();

  // Create the markdown export function
  const exportMarkdown = createMarkdownExport(MARKDOWN_TRANSFORMERS);

  // Export each top-level node by finding it in the root's children
  const markdownParts: string[] = [];
  const allChildren = root.getChildren();

  topLevelNodes.forEach((targetNode) => {
    // Find the index of this node in root's children
    const nodeIndex = allChildren.findIndex((child) => child.getKey() === targetNode.getKey());

    if (nodeIndex !== -1 && $isElementNode(targetNode)) {
      // Create a temporary root-like structure with just this one child
      // by using the export function on a virtual parent
      const mockParent = {
        getChildren: () => [targetNode],
      } as ElementNode;

      const markdown = exportMarkdown(mockParent);

      if (markdown && markdown.trim()) {
        markdownParts.push(markdown.trim());
      }
    }
  });

  const result = markdownParts.join('\n\n');
  return result;
};

/**
 * Finds the top-level element node (direct child of root).
 * Returns null if the node is the root itself.
 */
const findTopLevelElementNode = (targetElement: ElementNode): ElementNode | null => {
  let element = targetElement;
  let parentElement = element.getParent();

  while (parentElement && !$isRootNode(parentElement)) {
    element = parentElement as ElementNode;
    parentElement = element.getParent();
  }

  // Ensure we don't return the root itself
  return $isRootNode(element) ? null : element;
};

/**
 * Parses markdown string into Lexical nodes.
 * Uses a temporary conversion to avoid disrupting the existing editor state.
 */
const parseMarkdownToNodes = (root: ElementNode, markdown: string): LexicalNode[] => {
  // Save current root children
  const currentChildren = root.getChildren();
  const savedChildren = [...currentChildren];

  // Clear root and convert markdown, preserving newlines so empty lines become empty paragraphs
  root.clear();
  $convertFromMarkdownString(markdown, MARKDOWN_TRANSFORMERS, undefined, true);

  // Get the newly created nodes
  const newNodes = root.getChildren();
  const newNodesArray = [...newNodes];

  // Remove new nodes from root
  newNodesArray.forEach((node) => node.remove());

  // Restore the original children
  savedChildren.forEach((child) => root.append(child));

  return newNodesArray;
};

/**
 * Selects the end of the last node in the array.
 */
const selectEndOfLastNode = (nodes: LexicalNode[]): void => {
  if (nodes.length > 0) {
    const lastInsertedNode = nodes[nodes.length - 1];
    if ($isElementNode(lastInsertedNode)) {
      lastInsertedNode.selectEnd();
    }
  }
};

/**
 * Handles pasting markdown content into the editor.
 * Returns true when the custom handler processed the paste event so Lexical
 * can skip its default pipeline.
 */
const handlePasteAsMarkdown = (editor: ReturnType<typeof useLexicalComposerContext>[0], e: ClipboardEvent): boolean => {
  const { clipboardData } = e;
  if (!clipboardData) {
    return false;
  }

  const data = clipboardData.getData('text/plain');
  if (!data) {
    return false;
  }

  const clipboardTypes = clipboardData.types ? Array.from(clipboardData.types) : [];
  const hasLexicalPayload = clipboardTypes.includes('application/x-lexical-editor');
  const hasHtmlPayload = clipboardTypes.includes('text/html');

  const containsMarkdownIndicators =
    data.includes('\n') ||
    /^#{1,6}\s/.test(data) || // Headings
    /^\s*[-*+]\s/.test(data) || // List items
    /^\s*\d+\.\s/.test(data) || // Numbered lists
    /^\s*>\s/.test(data) || // Blockquotes
    /^```/.test(data) || // Code blocks
    /^\s*\|/.test(data); // Tables

  const isSimpleText = !containsMarkdownIndicators;

  // If the clipboard already has Lexical payload or rich HTML (and no markdown),
  // let the native handler keep the formatting.
  if (hasLexicalPayload || (hasHtmlPayload && isSimpleText)) {
    return false;
  }

  e.preventDefault();

  editor.update(
    () => {
      const selection = $getSelection();
      if (!$isRangeSelection(selection)) return;

      const anchorNode = selection.anchor.getNode();
      let targetElement: ElementNode | null = $isElementNode(anchorNode) ? anchorNode : anchorNode.getParent();

      if (!targetElement || !$isElementNode(targetElement)) return;

      // For simple text with collapsed selection in the middle of content, insert inline
      const isCollapsed = selection.isCollapsed();
      const targetHasContent = targetElement.getTextContentSize() > 0;

      if (isSimpleText && targetHasContent) {
        if (!isCollapsed) {
          selection.removeText();
        }
        selection.insertText(data);
        return;
      }

      // For complex markdown or empty blocks, use block-level insertion
      targetElement = findTopLevelElementNode(targetElement);
      if (!targetElement) return;

      const root = $getRoot();
      const targetIndex = targetElement.getIndexWithinParent();

      let willBeEmpty = false;
      if (!isCollapsed) {
        selection.removeText();
        willBeEmpty = targetElement.getTextContentSize() === 0;
      } else {
        willBeEmpty = targetElement.getTextContentSize() === 0;
      }

      const newNodes = parseMarkdownToNodes(root, data);
      const insertPosition = willBeEmpty ? targetIndex : targetIndex + 1;

      if (willBeEmpty) {
        targetElement.remove();
      }

      root.splice(insertPosition, 0, newNodes);
      selectEndOfLastNode(newNodes);
    },
    { discrete: true },
  );

  return true;
};

/**
 * Plugin that enables markdown-aware copy and paste functionality.
 * - When copying, converts selected blocks to markdown format
 * - When pasting, parses markdown and inserts as proper Lexical nodes
 */
export const MarkdownClipboardPlugin = (): null => {
  const [editor] = useLexicalComposerContext();

  useEffect(() => {
    // Register Lexical copy command handler with high priority to override default behavior
    const unregisterCopyCommand = editor.registerCommand(
      COPY_COMMAND,
      (event: ClipboardEvent) => {
        const selection = $getSelection();
        if (!$isRangeSelection(selection)) {
          return false;
        }

        const selectedNodes = selection.getNodes();

        // Only handle full block selections; let Lexical handle partial selections
        if (!isFullBlockSelection(selection, selectedNodes)) {
          return false;
        }

        const markdown = exportSelectedNodesAsMarkdown(selectedNodes);

        if (event.clipboardData) {
          event.preventDefault();
          event.clipboardData.clearData();
          event.clipboardData.setData('text/plain', markdown);
          return true;
        }

        return false;
      },
      COMMAND_PRIORITY_HIGH,
    );

    // Register Lexical paste command handler with high priority
    const unregisterPasteCommand = editor.registerCommand(
      PASTE_COMMAND,
      (e: ClipboardEvent) => handlePasteAsMarkdown(editor, e),
      COMMAND_PRIORITY_HIGH,
    );

    return () => {
      unregisterCopyCommand();
      unregisterPasteCommand();
    };
  }, [editor]);

  return null;
};
