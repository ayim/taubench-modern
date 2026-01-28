/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-nested-ternary */
/* eslint-disable no-restricted-syntax */
/* eslint-disable no-useless-concat */
/* eslint-disable prefer-template */
/* eslint-disable no-continue */
/* eslint-disable no-else-return */
/* eslint-disable no-use-before-define */

import type { ListType } from '@lexical/list';
import type { HeadingTagType } from '@lexical/rich-text';

import {
  $createLineBreakNode,
  $createParagraphNode,
  $createTextNode,
  $isElementNode,
  $isTextNode,
  ElementNode,
  Klass,
  LexicalNode,
  TextFormatType,
  TextNode,
} from 'lexical';

import { ELEMENT_TRANSFORMERS, TEXT_FORMAT_TRANSFORMERS } from '@lexical/markdown';
import {
  $createHorizontalRuleNode,
  $isHorizontalRuleNode,
  HorizontalRuleNode,
} from '@lexical/react/LexicalHorizontalRuleNode';
import {
  $isTableNode,
  $isTableRowNode,
  $isTableCellNode,
  TableNode,
  TableRowNode,
  TableCellNode,
} from '@lexical/table';

import { $createCodeNode, $isCodeNode, CodeNode } from '@lexical/code';
import { $createLinkNode, $isLinkNode, LinkNode } from '@lexical/link';
import {
  $createListItemNode,
  $createListNode,
  $isListItemNode,
  $isListNode,
  ListItemNode,
  ListNode,
} from '@lexical/list';
import {
  $createHeadingNode,
  $createQuoteNode,
  $isHeadingNode,
  $isQuoteNode,
  HeadingNode,
  QuoteNode,
} from '@lexical/rich-text';

export type Transformer = ElementTransformer | TextFormatTransformer | TextMatchTransformer;

export type ElementTransformer = {
  dependencies: Array<Klass<LexicalNode>>;
  export: (
    node: LexicalNode,

    traverseChildren: (node: ElementNode) => string,
  ) => string | null;
  regExp: RegExp;
  replace: (parentNode: ElementNode, children: Array<LexicalNode>, match: Array<string>, isImport: boolean) => void;
  type: 'element';
};

export type TextFormatTransformer = Readonly<{
  format: ReadonlyArray<TextFormatType>;
  tag: string;
  intraword?: boolean;
  type: 'text-format';
}>;

export type TextMatchTransformer = Readonly<{
  dependencies: Array<Klass<LexicalNode>>;
  export: (
    node: LexicalNode,

    exportChildren: (node: ElementNode) => string,

    exportFormat: (node: TextNode, textContent: string) => string,
  ) => string | null;
  importRegExp: RegExp;
  regExp: RegExp;
  replace: (node: TextNode, match: RegExpMatchArray) => void;
  trigger: string;
  type: 'text-match';
}>;

const createBlockNode = (createNode: (match: Array<string>) => ElementNode): ElementTransformer['replace'] => {
  return (parentNode, children, match) => {
    const node = createNode(match);
    node.append(...children);
    parentNode.replace(node);
    node.select(0, 0);
  };
};

// Amount of spaces that define indentation level
// TODO: should be an option
const LIST_INDENT_SIZE = 2;

function getIndent(whitespaces: string): number {
  const tabs = whitespaces.match(/\t/g);
  const spaces = whitespaces.match(/ /g);

  let indent = 0;

  if (tabs) {
    indent += tabs.length;
  }

  if (spaces) {
    indent += Math.floor(spaces.length / LIST_INDENT_SIZE);
  }

  return indent;
}

const listReplace = (listType: ListType): ElementTransformer['replace'] => {
  return (parentNode, children, match) => {
    const previousNode = parentNode.getPreviousSibling();
    const nextNode = parentNode.getNextSibling();
    const listItem = $createListItemNode(listType === 'check' ? match[3] === 'x' : undefined);
    const indent = getIndent(match[1]);

    // Wrap children in a paragraph node for proper list item structure
    const paragraph = $createParagraphNode();
    paragraph.append(...children);
    listItem.append(paragraph);

    if ($isListNode(nextNode) && nextNode.getListType() === listType) {
      const firstChild = nextNode.getFirstChild();
      if (firstChild !== null) {
        firstChild.insertBefore(listItem);
      } else {
        nextNode.append(listItem);
      }
      parentNode.remove();
    } else if ($isListNode(previousNode) && previousNode.getListType() === listType) {
      if (indent === 0) {
        // Top-level item, append to previous list
        previousNode.append(listItem);
        parentNode.remove();
      } else {
        // Nested item - find the last item in the previous list and nest under it
        let targetList: ListNode = previousNode;
        let currentDepth = 0;

        // Navigate to the correct nesting level
        while (currentDepth < indent) {
          const lastChild = targetList.getLastChild();

          if (!$isListItemNode(lastChild)) {
            // Can't nest if there's no parent item, fallback to top level
            previousNode.append(listItem);
            parentNode.remove();
            listItem.select(0, 0);
            return;
          }

          // Check if this item already has a nested list
          let nestedList: ListNode | null = null;
          const lastChildren = lastChild.getChildren();

          for (const child of lastChildren) {
            if ($isListNode(child) && child.getListType() === listType) {
              nestedList = child;
              break;
            }
          }

          if (nestedList) {
            targetList = nestedList;
          } else {
            // Create a new nested list
            nestedList = $createListNode(listType, listType === 'number' ? 1 : undefined);
            lastChild.append(nestedList);
            targetList = nestedList;
          }

          currentDepth += 1;
        }

        targetList.append(listItem);
        parentNode.remove();
      }
    } else {
      // No adjacent list, create new one (should only happen for non-nested items)
      const list = $createListNode(listType, listType === 'number' ? Number(match[2]) : undefined);
      list.append(listItem);
      parentNode.replace(list);
    }

    listItem.select(0, 0);
  };
};

const listExport = (listNode: ListNode, exportChildren: (node: ElementNode) => string, depth: number): string => {
  const output = [];
  const children = listNode.getChildren();
  let index = 0;

  for (const listItemNode of children) {
    if ($isListItemNode(listItemNode)) {
      const indent = ' '.repeat(depth * LIST_INDENT_SIZE);
      const listType = listNode.getListType();
      const prefix =
        listType === 'number'
          ? `${listNode.getStart() + index}. `
          : listType === 'check'
            ? `- [${listItemNode.getChecked() ? 'x' : ' '}] `
            : '- ';

      // Find nested lists and get text content (excluding nested lists)
      let textContent = '';
      let nestedListNode: ListNode | null = null;

      const itemChildren = listItemNode.getChildren();
      for (const child of itemChildren) {
        if ($isListNode(child)) {
          nestedListNode = child;
        } else {
          // Export only the paragraph/element content, not nested lists
          // Type assertion since we know it's an ElementNode if it's not a ListNode
          try {
            const content = exportChildren(child as ElementNode);
            if (content) {
              textContent += content;
            }
          } catch (e) {
            // Fallback to text content if export fails
            textContent += child.getTextContent();
          }
        }
      }

      // Output the current item text
      output.push(indent + prefix + textContent);

      // If there's a nested list, export it recursively
      if (nestedListNode) {
        output.push(listExport(nestedListNode, exportChildren, depth + 1));
      }

      index += 1;
    }
  }

  return output.join('\n');
};

export const HR: ElementTransformer = {
  dependencies: [HorizontalRuleNode],
  export: (node: LexicalNode) => {
    return $isHorizontalRuleNode(node) ? '***' : null;
  },
  regExp: /^(---|\*\*\*|___)\s?$/,
  replace: (parentNode, _1, _2, isImport) => {
    const line = $createHorizontalRuleNode();

    // TODO: Get rid of isImport flag
    if (isImport || parentNode.getNextSibling() != null) {
      parentNode.replace(line);
    } else {
      parentNode.insertBefore(line);
    }

    line.selectNext();
  },
  type: 'element',
};

export const TABLE: ElementTransformer = {
  dependencies: [TableNode, TableRowNode, TableCellNode],
  export: (node: LexicalNode, exportChildren) => {
    if (!$isTableNode(node)) {
      return null;
    }

    const output: string[] = [];
    const rows = node.getChildren();
    let isFirstRow = true;

    for (const row of rows) {
      if (!$isTableRowNode(row)) {
        continue;
      }

      const cells = row.getChildren();
      const cellContents: string[] = [];

      for (const cell of cells) {
        if (!$isTableCellNode(cell)) {
          continue;
        }

        // Get the text content of the cell, removing any newlines
        const cellText = exportChildren(cell).replace(/\n/g, ' ').trim();
        cellContents.push(cellText);
      }

      // Build the row with pipes
      if (cellContents.length > 0) {
        output.push(`| ${cellContents.join(' | ')} |`);

        // Add separator row after the first row (header row)
        if (isFirstRow) {
          const separator = cellContents.map(() => '--------').join(' | ');
          output.push(`| ${separator} |`);
          isFirstRow = false;
        }
      }
    }

    return output.length > 0 ? output.join('\n') : null;
  },
  regExp: /^\|(.+)\|$/,
  replace: () => {
    // Table import is handled at a higher level in MarkdownImport.ts
    // This replace function is not used during import, only for typing transformations
  },
  type: 'element',
};

export const HEADING: ElementTransformer = {
  dependencies: [HeadingNode],
  export: (node, exportChildren) => {
    if (!$isHeadingNode(node)) {
      return null;
    }
    const level = Number(node.getTag().slice(1));
    return '#'.repeat(level) + ' ' + exportChildren(node);
  },
  regExp: /^(#{1,6})\s/,
  replace: createBlockNode((match) => {
    const tag = ('h' + match[1].length) as HeadingTagType;
    return $createHeadingNode(tag);
  }),
  type: 'element',
};

export const QUOTE: ElementTransformer = {
  dependencies: [QuoteNode],
  export: (node, exportChildren) => {
    if (!$isQuoteNode(node)) {
      return null;
    }

    const lines = exportChildren(node).split('\n');
    const output = [];
    for (const line of lines) {
      output.push('> ' + line);
    }
    return output.join('\n');
  },
  regExp: /^>\s/,
  replace: (parentNode, children, _match, isImport) => {
    if (isImport) {
      const previousNode = parentNode.getPreviousSibling();
      if ($isQuoteNode(previousNode)) {
        previousNode.splice(previousNode.getChildrenSize(), 0, [$createLineBreakNode(), ...children]);
        previousNode.select(0, 0);
        parentNode.remove();
        return;
      }
    }

    const node = $createQuoteNode();
    node.append(...children);
    parentNode.replace(node);
    node.select(0, 0);
  },
  type: 'element',
};

export const CODE: ElementTransformer = {
  dependencies: [CodeNode],
  export: (node: LexicalNode) => {
    if (!$isCodeNode(node)) {
      return null;
    }
    const textContent = node.getTextContent();
    return '```' + (node.getLanguage() || '') + (textContent ? '\n' + textContent : '') + '\n' + '```';
  },
  regExp: /^[ \t]*```(\w{1,10})?\s/,
  replace: createBlockNode((match) => {
    return $createCodeNode(match ? match[1] : undefined);
  }),
  type: 'element',
};

export const UNORDERED_LIST: ElementTransformer = {
  dependencies: [ListNode, ListItemNode],
  export: (node, exportChildren) => {
    return $isListNode(node) ? listExport(node, exportChildren, 0) : null;
  },
  regExp: /^(\s*)[-*+]\s/,
  replace: listReplace('bullet'),
  type: 'element',
};

export const CHECK_LIST: ElementTransformer = {
  dependencies: [ListNode, ListItemNode],
  export: (node, exportChildren) => {
    return $isListNode(node) ? listExport(node, exportChildren, 0) : null;
  },
  regExp: /^(\s*)(?:-\s)?\s?(\[(\s|x)?\])\s/i,
  replace: listReplace('check'),
  type: 'element',
};

export const ORDERED_LIST: ElementTransformer = {
  dependencies: [ListNode, ListItemNode],
  export: (node, exportChildren) => {
    return $isListNode(node) ? listExport(node, exportChildren, 0) : null;
  },
  regExp: /^(\s*)(\d{1,})\.\s/,
  replace: listReplace('number'),
  type: 'element',
};

export const INLINE_CODE: TextFormatTransformer = {
  format: ['code'],
  tag: '`',
  type: 'text-format',
};

export const HIGHLIGHT: TextFormatTransformer = {
  format: ['highlight'],
  tag: '==',
  type: 'text-format',
};

export const BOLD_ITALIC_STAR: TextFormatTransformer = {
  format: ['bold', 'italic'],
  tag: '***',
  type: 'text-format',
};

export const BOLD_ITALIC_UNDERSCORE: TextFormatTransformer = {
  format: ['bold', 'italic'],
  intraword: false,
  tag: '___',
  type: 'text-format',
};

export const BOLD_STAR: TextFormatTransformer = {
  format: ['bold'],
  tag: '**',
  type: 'text-format',
};

export const BOLD_UNDERSCORE: TextFormatTransformer = {
  format: ['bold'],
  intraword: false,
  tag: '__',
  type: 'text-format',
};

export const STRIKETHROUGH: TextFormatTransformer = {
  format: ['strikethrough'],
  tag: '~~',
  type: 'text-format',
};

export const ITALIC_STAR: TextFormatTransformer = {
  format: ['italic'],
  tag: '*',
  type: 'text-format',
};

export const ITALIC_UNDERSCORE: TextFormatTransformer = {
  format: ['italic'],
  intraword: false,
  tag: '_',
  type: 'text-format',
};

// Order of text transformers matters:
//
// - code should go first as it prevents any transformations inside
// - then longer tags match (e.g. ** or __ should go before * or _)
export const LINK: TextMatchTransformer = {
  dependencies: [LinkNode],
  export: (node, _exportChildren, exportFormat) => {
    if (!$isLinkNode(node)) {
      return null;
    }
    const title = node.getTitle();
    const linkContent = title
      ? `[${node.getTextContent()}](${node.getURL()} "${title}")`
      : `[${node.getTextContent()}](${node.getURL()})`;
    const firstChild = node.getFirstChild();
    // Add text styles only if link has single text node inside. If it's more
    // then one we ignore it as markdown does not support nested styles for links
    if (node.getChildrenSize() === 1 && $isTextNode(firstChild)) {
      return exportFormat(firstChild, linkContent);
    } else {
      return linkContent;
    }
  },
  importRegExp: /(?:\[([^[]+)\])(?:\((?:([^()\s]+)(?:\s"((?:[^"]*\\")*[^"]*)"\s*)?)\))/,
  regExp: /(?:\[([^[]+)\])(?:\((?:([^()\s]+)(?:\s"((?:[^"]*\\")*[^"]*)"\s*)?)\))$/,
  replace: (textNode, match) => {
    const [, linkText, linkUrl, linkTitle] = match;
    const linkNode = $createLinkNode(linkUrl, { title: linkTitle });
    const linkTextNode = $createTextNode(linkText);
    linkTextNode.setFormat(textNode.getFormat());
    linkNode.append(linkTextNode);
    textNode.replace(linkNode);
  },
  trigger: ')',
  type: 'text-match',
};

export const MARKDOWN_TRANSFORMERS: Array<Transformer> = [
  TABLE,
  HR,
  HEADING,
  QUOTE,
  LINK,
  INLINE_CODE,
  ORDERED_LIST,
  UNORDERED_LIST,
  CODE,
  CHECK_LIST,
  HIGHLIGHT,
  BOLD_ITALIC_STAR,
  BOLD_ITALIC_UNDERSCORE,
  BOLD_STAR,
  BOLD_UNDERSCORE,
  STRIKETHROUGH,
  ITALIC_STAR,
  ITALIC_UNDERSCORE,
  ...ELEMENT_TRANSFORMERS,
  ...TEXT_FORMAT_TRANSFORMERS,
];

export const staticConvertNodeToMarkdown = (node: LexicalNode): string => {
  // Try each transformer to see if it can handle this node
  for (const transformer of MARKDOWN_TRANSFORMERS) {
    if (transformer.type === 'element' && $isElementNode(node)) {
      // Call the transformer's export function
      const result = transformer.export(node, (childNode: ElementNode) => {
        // Recursively get text content of children
        return childNode.getTextContent();
      });

      if (result !== null) {
        return result;
      }
    }
  }

  // Fallback: return text content
  return node.getTextContent();
};
