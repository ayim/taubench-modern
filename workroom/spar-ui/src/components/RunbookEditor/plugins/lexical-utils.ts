/* eslint-disable no-restricted-syntax */
import Fuse from 'fuse.js';
import { $getRoot, $isRootNode, LexicalNode, TextNode, $isElementNode, ElementNode } from 'lexical';
import { closestMatch } from 'leven';
import { $isListItemNode, $isListNode } from '@lexical/list';
import { $isTableCellNode } from '@lexical/table';
import { $isQuoteNode } from '@lexical/rich-text';
import { $isCodeNode } from '@lexical/code';
import { SuggestionNode } from './nodes/SuggestionNode';

export const FUSE_THRESHOLD = 0.2; // 0.0 = perfect match, 1.0 = no match. Strict matching with 0.2 threshold

/**
 * Finds the ancestor of a given node.
 * @param node The node to find the ancestor of
 * @returns The ancestor node or null if no ancestor found
 */
export function findAncestor(node: LexicalNode): LexicalNode | null {
  let currentNode: LexicalNode | null = node;
  while (currentNode) {
    const parent: LexicalNode | null = currentNode.getParent();
    if (parent === $getRoot()) {
      return currentNode;
    }
    currentNode = parent;
  }
  return null;
}

/**
 * Helper function to find the appropriate ancestor node to replace
 * based on the type of the new nodes being inserted
 * Returns an object with the ancestor to replace and optionally modified nodes
 */
export function findAppropriateAncestorToReplace(
  suggestionNode: SuggestionNode,
  newNodes: LexicalNode[],
): { ancestor: LexicalNode | null; nodesToInsert: LexicalNode[] } {
  // If no new nodes, fall back to top-level ancestor
  if (newNodes.length === 0) {
    return { ancestor: findAncestor(suggestionNode), nodesToInsert: newNodes };
  }

  // Check what type of node we're replacing with
  const firstNewNode = newNodes[0];

  // First, check if we're inside a list item, regardless of what we're replacing it with
  // This ensures that when a paragraph replaces a list item, we only replace that item, not the entire list
  let ancestorCheck: LexicalNode | null = suggestionNode;
  let listItemAncestor: LexicalNode | null = null;

  while (ancestorCheck) {
    const parent: LexicalNode | null = ancestorCheck.getParent();
    if (!parent) {
      break;
    }
    if ($isListItemNode(parent)) {
      listItemAncestor = parent;
      break;
    }
    if ($isRootNode(parent)) {
      break;
    }
    ancestorCheck = parent;
  }

  // Special handling for lists
  // When markdown like "3. item" is parsed, it creates a ListNode containing ListItemNode(s)
  // But we want to replace just the specific ListItemNode, not the entire list
  if ($isListNode(firstNewNode)) {
    if (listItemAncestor) {
      // Extract the list items from the new ListNode
      // We need to get the children but they're still attached to the ListNode
      // We'll return the ListNode children which will be properly detached during insertion
      const listItems = firstNewNode.getChildren();
      return { ancestor: listItemAncestor, nodesToInsert: listItems };
    }
    // If we're not inside a list item, return the current top-level ancestor with the list
    return { ancestor: findAncestor(suggestionNode), nodesToInsert: newNodes };
  }

  // Special handling for list items - we want to replace just the list item, not the entire list
  if ($isListItemNode(firstNewNode)) {
    if (listItemAncestor) {
      return { ancestor: listItemAncestor, nodesToInsert: newNodes };
    }
    // If we're not inside a list item, return the current top-level ancestor
    return { ancestor: findAncestor(suggestionNode), nodesToInsert: newNodes };
  }

  // If we're inside a list item and replacing with a non-list node (e.g., paragraph),
  // we still want to replace just the list item
  if (listItemAncestor) {
    return { ancestor: listItemAncestor, nodesToInsert: newNodes };
  }

  // Special handling for tables - we want to replace only the cell content, not the entire table
  // Check if we're inside a table cell
  let currentNode: LexicalNode | null = suggestionNode;
  while (currentNode) {
    const parent: LexicalNode | null = currentNode.getParent();
    if (!parent) {
      break;
    }
    if ($isTableCellNode(parent)) {
      // We found a table cell - this is what we should replace the content of
      // Return the first child of the cell (usually a paragraph) as the ancestor
      return { ancestor: currentNode, nodesToInsert: newNodes };
    }
    if ($isRootNode(parent)) {
      break;
    }
    currentNode = parent;
  }

  // For other block-level elements (quotes, code blocks, headings, etc.)
  // Find a matching ancestor or return the top-level ancestor
  currentNode = suggestionNode;

  while (currentNode) {
    const parent: LexicalNode | null = currentNode.getParent();
    if (!parent || $isRootNode(parent)) {
      // We've reached the root, return the current node (top-level ancestor)
      return { ancestor: currentNode, nodesToInsert: newNodes };
    }

    // Check if the parent matches the type we're replacing with
    if ($isQuoteNode(firstNewNode) && $isQuoteNode(parent)) {
      return { ancestor: parent, nodesToInsert: newNodes };
    }
    if ($isCodeNode(firstNewNode) && $isCodeNode(parent)) {
      return { ancestor: parent, nodesToInsert: newNodes };
    }

    currentNode = parent;
  }

  // Fallback: return top-level ancestor
  return { ancestor: findAncestor(suggestionNode), nodesToInsert: newNodes };
}

/**
 * Normalizes whitespace in a string by replacing multiple consecutive spaces with a single space
 * @param text The text to normalize
 * @returns The text with normalized whitespace
 */
const normalizeWhitespace = (text: string): string => {
  return text.replace(/\s+/g, ' ').trim();
};

/**
 * Attempts to find an exact match for the target text among the provided nodes.
 * @param targetText The text to search for (trimmed)
 * @param nodes Array of text nodes to search through
 * @returns The exactly matching text node or null if no exact match found
 */
const findExactMatchNode = (targetText: string, nodes: TextNode[]): TextNode | null => {
  const normalizedTarget = normalizeWhitespace(targetText);

  const exactMatch = closestMatch(
    normalizedTarget,
    nodes.map((n) => normalizeWhitespace(n.getTextContent())),
    { maxDistance: 0 },
  );

  if (exactMatch) {
    const matchIndex = nodes.findIndex((n) => normalizeWhitespace(n.getTextContent()) === exactMatch);
    if (matchIndex !== -1) {
      return nodes[matchIndex];
    }
  }

  return null;
};

/**
 * Performs fuzzy matching using fuse.js to find the best matching node.
 * @param targetText The text to search for (trimmed)
 * @param nodes Array of text nodes to search through
 * @returns The best fuzzy-matched text node or null if no match meets threshold
 */
const findFuzzyMatchNode = (
  targetText: string,
  nodes: TextNode[],
  threshold: number = FUSE_THRESHOLD,
): TextNode | null => {
  const normalizedTarget = normalizeWhitespace(targetText);

  const nodesWithText = nodes.map((node, index) => ({
    node,
    text: normalizeWhitespace(node.getTextContent()),
    index,
  }));

  const fuse = new Fuse(nodesWithText, {
    keys: ['text'],
    threshold,
    includeScore: true,
    distance: 1000, // Allow matching even if characters are far apart
    ignoreLocation: true, // Don't care where in the string the match occurs
  });

  const results = fuse.search(normalizedTarget);

  // Return the best match (lowest score = best match in fuse.js)
  if (results.length > 0 && results[0].score !== undefined && results[0].score <= threshold) {
    return results[0].item.node;
  }

  return null;
};

/**
 * Collects all unique parent elements from text nodes
 * This helps us search at the element level rather than individual text node level
 */
const getUniqueParentElements = (textNodes: TextNode[]): ElementNode[] => {
  const parentSet = new Set<ElementNode>();

  for (const node of textNodes) {
    try {
      const parent = node.getParent();
      if (parent && $isElementNode(parent) && !$isRootNode(parent)) {
        parentSet.add(parent);
      }
    } catch {
      // Node is no longer in the tree, skip it
    }
  }

  return Array.from(parentSet);
};

/**
 * Finds the first text node in an element that matches the search text
 * This is used when we find a parent element whose combined text matches our search
 */
const findFirstTextNodeInElement = (element: ElementNode, targetText: string): TextNode | null => {
  const textNodes = element.getAllTextNodes();
  if (textNodes.length === 0) {
    return null;
  }

  // If there's only one text node, return it
  if (textNodes.length === 1) {
    return textNodes[0];
  }

  // Find the text node that contains the start of our target text
  const normalizedTarget = normalizeWhitespace(targetText);
  const targetStart = normalizedTarget.split(/\s+/)[0]; // First word

  for (const node of textNodes) {
    const nodeText = normalizeWhitespace(node.getTextContent());
    if (nodeText.includes(targetStart)) {
      return node;
    }
  }

  // Fallback: return first text node
  return textNodes[0];
};

/**
 * Searches for matching parent elements whose combined text content matches the target
 */
const findMatchingParentElement = (targetText: string, parentElements: ElementNode[]): ElementNode | null => {
  const normalizedTarget = normalizeWhitespace(targetText);

  // Try exact match first
  for (const parent of parentElements) {
    const parentText = normalizeWhitespace(parent.getTextContent());
    if (parentText === normalizedTarget) {
      return parent;
    }
  }

  // Try fuzzy match using Fuse
  const elementsWithText = parentElements.map((element, index) => ({
    element,
    text: normalizeWhitespace(element.getTextContent()),
    index,
  }));

  const fuse = new Fuse(elementsWithText, {
    keys: ['text'],
    threshold: FUSE_THRESHOLD,
    includeScore: true,
    distance: 1000,
    ignoreLocation: true,
  });

  const results = fuse.search(normalizedTarget);

  if (results.length > 0 && results[0].score !== undefined && results[0].score <= FUSE_THRESHOLD) {
    return results[0].item.element;
  }

  return null;
};

/**
 * Result type for text node matching that includes the matched text context
 */
export type MatchResult = {
  node: TextNode;
  matchedText: string; // The full text that was matched (may be from parent element)
  matchedAtParentLevel: boolean; // True if we matched at parent element level (multiple text nodes)
  parentElement?: ElementNode; // The parent element if matched at parent level
} | null;

/**
 * Finds the best matching text node using a hybrid approach:
 * 1. First searches at parent element level (to handle formatted text across multiple nodes)
 * 2. Falls back to individual text node search
 * @param targetText The text to search for (already stripped of markdown)
 * @param textNodes Array of text nodes to search through
 * @returns Match result with node and matched text, or null if no match meets threshold
 */
export const findBestMatchingNode = (targetText: string, textNodes: TextNode[]): MatchResult => {
  if (!targetText || textNodes.length === 0) {
    return null;
  }

  const normalizedTarget = normalizeWhitespace(targetText);
  const validNodes: TextNode[] = [];

  // Filter to only valid nodes (still attached to tree)
  for (const node of textNodes) {
    try {
      const parent = node.getParent();
      if (parent) {
        validNodes.push(node);
      }
    } catch {
      // Node is no longer in the tree, skip it
    }
  }

  if (validNodes.length === 0) {
    return null;
  }

  // Step 1: Try to find a matching parent element (handles formatted text)
  const parentElements = getUniqueParentElements(validNodes);
  const matchingParent = findMatchingParentElement(normalizedTarget, parentElements);

  if (matchingParent) {
    // Found a parent element whose combined text matches
    // Return the first text node in this element along with the full parent text
    const firstTextNode = findFirstTextNodeInElement(matchingParent, normalizedTarget);
    if (firstTextNode) {
      return {
        node: firstTextNode,
        matchedText: matchingParent.getTextContent(),
        matchedAtParentLevel: true,
        parentElement: matchingParent,
      };
    }
  }

  // Step 2: Fall back to individual text node matching (for single-node text)
  const exactMatch = findExactMatchNode(normalizedTarget, validNodes);
  if (exactMatch) {
    return {
      node: exactMatch,
      matchedText: exactMatch.getTextContent(),
      matchedAtParentLevel: false,
    };
  }

  // Step 3: Final fallback to fuzzy matching on individual nodes
  const fuzzyMatch = findFuzzyMatchNode(normalizedTarget, validNodes);
  if (fuzzyMatch) {
    return {
      node: fuzzyMatch,
      matchedText: fuzzyMatch.getTextContent(),
      matchedAtParentLevel: false,
    };
  }

  return null;
};
