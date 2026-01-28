/* eslint-disable no-restricted-syntax */
/* eslint-disable no-labels */
/* eslint-disable no-continue */
/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck

import type { CodeNode } from '@lexical/code';
import type { ElementTransformer, TextFormatTransformer, TextMatchTransformer, Transformer } from '@lexical/markdown';
import type { TextNode } from 'lexical';

import { $createCodeNode } from '@lexical/code';
import { $isListItemNode, $isListNode, ListItemNode } from '@lexical/list';
import { $isQuoteNode } from '@lexical/rich-text';
import { $findMatchingParent, IS_APPLE_WEBKIT, IS_IOS, IS_SAFARI } from '@lexical/utils';
import {
  $createLineBreakNode,
  $createParagraphNode,
  $createTextNode,
  $getRoot,
  $getSelection,
  $isParagraphNode,
  $isRootNode,
  ElementNode,
} from 'lexical';
import {
  $createTableNode,
  $createTableRowNode,
  $createTableCellNode,
  TableNode,
  TableCellHeaderStates,
} from '@lexical/table';

import { isEmptyParagraph, PUNCTUATION_OR_SPACE, transformersByType } from './utils';

const CODE_BLOCK_REG_EXP = /^[ \t]*```(\w{1,10})?\s?$/;
const TABLE_ROW_REG_EXP = /^\|(.+)\|$/;
const TABLE_ROW_DIVIDER_REG_EXP = /^\|[\s\-:|]+\|$/;

type TextFormatTransformersIndex = Readonly<{
  fullMatchRegExpByTag: Readonly<Record<string, RegExp>>;
  openTagsRegExp: RegExp;
  transformersByTag: Readonly<Record<string, TextFormatTransformer>>;
}>;

/**
 * Renders markdown from a string. The selection is moved to the start after the operation.
 */
export function createMarkdownImport(
  transformers: Array<Transformer>,
  shouldPreserveNewLines = false,
): (markdownString: string, node?: ElementNode) => void {
  const byType = transformersByType(transformers);
  const textFormatTransformersIndex = createTextFormatTransformersIndex(byType.textFormat);

  return (markdownString, node) => {
    const lines = markdownString.split('\n');
    const linesLength = lines.length;
    const root = node || $getRoot();
    root.clear();

    for (let i = 0; i < linesLength; i += 1) {
      const lineText = lines[i];

      // Codeblocks are processed first as anything inside such block
      // is ignored for further processing
      // TODO:
      // Abstract it to be dynamic as other transformers (add multiline match option)
      const [codeBlockNode, shiftedIndex] = $importCodeBlock(lines, i, root);
      if (codeBlockNode != null) {
        i = shiftedIndex;
        continue;
      }

      // Tables are processed before regular blocks as they span multiple lines
      const [tableNode, tableShiftedIndex] = $importTableBlock(lines, i, root);
      if (tableNode != null) {
        i = tableShiftedIndex;
        continue;
      }

      $importBlocks(lineText, root, byType.element, textFormatTransformersIndex, byType.textMatch);
    }

    // By default, removing empty paragraphs as md does not really
    // allow empty lines and uses them as delimiter.
    // If you need empty lines set shouldPreserveNewLines = true.
    const realRoot = $getRoot();
    const children = realRoot.getChildren();
    for (const child of children) {
      if (!shouldPreserveNewLines && isEmptyParagraph(child) && realRoot.getChildrenSize() > 1) {
        child.remove();
      }
    }

    // By default, remove the empty paragraphs as above
    // but for the given node & not the root
    if (node) {
      const nodeChildren = node.getChildren();
      for (const child of nodeChildren) {
        if (!shouldPreserveNewLines && isEmptyParagraph(child) && node.getChildrenSize() > 1) {
          child.remove();
        }
      }
    }

    if ($getSelection() !== null) {
      realRoot.selectStart();
    }
  };
}

function $importBlocks(
  lineText: string,
  rootNode: ElementNode,
  elementTransformers: Array<ElementTransformer>,
  textFormatTransformersIndex: TextFormatTransformersIndex,
  textMatchTransformers: Array<TextMatchTransformer>,
) {
  const textNode = $createTextNode(lineText);
  const elementNode = $createParagraphNode();
  elementNode.append(textNode);
  if ($isRootNode(rootNode)) {
    rootNode.append(elementNode);
  } else {
    rootNode.append(elementNode);
  }

  for (const { regExp, replace } of elementTransformers) {
    const match = lineText.match(regExp);

    if (match) {
      textNode.setTextContent(lineText.slice(match[0].length));
      replace(elementNode, [textNode], match, true);
      break;
    }
  }

  importTextFormatTransformers(textNode, textFormatTransformersIndex, textMatchTransformers);

  // If no transformer found and we left with original paragraph node
  // can check if its content can be appended to the previous node
  // if it's a paragraph, quote or list
  if (elementNode.isAttached() && lineText.length > 0) {
    const previousNode = elementNode.getPreviousSibling();
    if ($isParagraphNode(previousNode) || $isQuoteNode(previousNode) || $isListNode(previousNode)) {
      let targetNode: typeof previousNode | ListItemNode | null = previousNode;

      if ($isListNode(previousNode)) {
        const lastDescendant = previousNode.getLastDescendant();
        if (lastDescendant == null) {
          targetNode = null;
        } else {
          targetNode = $findMatchingParent(lastDescendant, $isListItemNode);
        }
      }

      if (targetNode != null && targetNode.getTextContentSize() > 0) {
        targetNode.splice(targetNode.getChildrenSize(), 0, [$createLineBreakNode(), ...elementNode.getChildren()]);
        elementNode.remove();
      }
    }
  }
}

function $importCodeBlock(
  lines: Array<string>,
  startLineIndex: number,
  rootNode: ElementNode,
): [CodeNode | null, number] {
  const openMatch = lines[startLineIndex].match(CODE_BLOCK_REG_EXP);

  if (openMatch) {
    const endLineIndex = startLineIndex;
    const linesLength = lines.length;

    while (endLineIndex + 1 < linesLength) {
      const closeMatch = lines[endLineIndex].match(CODE_BLOCK_REG_EXP);

      if (closeMatch) {
        const codeBlockNode = $createCodeNode(openMatch[1]);
        const textNode = $createTextNode(lines.slice(startLineIndex + 1, endLineIndex).join('\n'));
        codeBlockNode.append(textNode);
        if ($isRootNode(rootNode)) {
          rootNode.append(codeBlockNode);
        } else {
          rootNode.append(codeBlockNode);
        }
        return [codeBlockNode, endLineIndex];
      }
    }
  }

  return [null, startLineIndex];
}

function $importTableBlock(
  lines: Array<string>,
  startLineIndex: number,
  rootNode: ElementNode,
): [TableNode | null, number] {
  const startLine = lines[startLineIndex];

  // Check if the current line looks like a table row
  if (!TABLE_ROW_REG_EXP.test(startLine)) {
    return [null, startLineIndex];
  }

  // Collect all consecutive table lines
  const tableLines: string[] = [startLine];
  let endLineIndex = startLineIndex;
  const linesLength = lines.length;

  while (endLineIndex + 1 < linesLength) {
    const line = lines[endLineIndex];
    if (TABLE_ROW_REG_EXP.test(line)) {
      tableLines.push(line);
    } else {
      // Stop when we hit a non-table line
      endLineIndex -= 1;
      break;
    }
  }

  // Need at least 2 lines for a valid table (header + separator minimum)
  if (tableLines.length < 2) {
    return [null, startLineIndex];
  }

  // Parse rows and detect separator
  const parsedRows: string[][] = [];
  let separatorIndex = -1;

  for (let i = 0; i < tableLines.length; i += 1) {
    const line = tableLines[i];

    // Check if this is a separator line
    if (TABLE_ROW_DIVIDER_REG_EXP.test(line)) {
      separatorIndex = i;
      continue;
    }

    // Parse cells from the line
    const cells = line
      .split('|')
      .slice(1, -1) // Remove empty strings from leading/trailing pipes
      .map((cell) => cell.trim());

    if (cells.length > 0) {
      parsedRows.push(cells);
    }
  }

  // Need at least one data row to create a table
  if (parsedRows.length === 0) {
    return [null, startLineIndex];
  }

  // Create the table node
  const tableNode = $createTableNode();

  // Create rows and cells
  parsedRows.forEach((cells, rowIndex) => {
    const rowNode = $createTableRowNode();

    cells.forEach((cellText) => {
      // First row is header if there's a separator after it
      const isHeader = separatorIndex === 1 && rowIndex === 0;
      const cellNode = $createTableCellNode(isHeader ? TableCellHeaderStates.ROW : TableCellHeaderStates.NO_STATUS);

      const paragraphNode = $createParagraphNode();
      if (cellText) {
        paragraphNode.append($createTextNode(cellText));
      }
      cellNode.append(paragraphNode);
      rowNode.append(cellNode);
    });

    tableNode.append(rowNode);
  });

  // Append table to root
  if ($isRootNode(rootNode)) {
    rootNode.append(tableNode);
  } else {
    rootNode.append(tableNode);
  }

  return [tableNode, endLineIndex];
}

// Processing text content and replaces text format tags.
// It takes outermost tag match and its content, creates text node with
// format based on tag and then recursively executed over node's content
//
// E.g. for "*Hello **world**!*" string it will create text node with
// "Hello **world**!" content and italic format and run recursively over
// its content to transform "**world**" part
function importTextFormatTransformers(
  textNode: TextNode,
  textFormatTransformersIndex: TextFormatTransformersIndex,
  textMatchTransformers: Array<TextMatchTransformer>,
) {
  const textContent = textNode.getTextContent();
  const match = findOutermostMatch(textContent, textFormatTransformersIndex);

  if (!match) {
    // Once text format processing is done run text match transformers, as it
    // only can span within single text node (unline formats that can cover multiple nodes)
    importTextMatchTransformers(textNode, textMatchTransformers);
    return;
  }

  let currentNode;
  let remainderNode;
  let leadingNode;

  // If matching full content there's no need to run splitText and can reuse existing textNode
  // to update its content and apply format. E.g. for **_Hello_** string after applying bold
  // format (**) it will reuse the same text node to apply italic (_)
  if (match[0] === textContent) {
    currentNode = textNode;
  } else {
    const startIndex = match.index || 0;
    const endIndex = startIndex + match[0].length;

    if (startIndex === 0) {
      [currentNode, remainderNode] = textNode.splitText(endIndex);
    } else {
      [leadingNode, currentNode, remainderNode] = textNode.splitText(startIndex, endIndex);
    }
  }

  currentNode.setTextContent(match[2]);
  const transformer = textFormatTransformersIndex.transformersByTag[match[1]];

  if (transformer) {
    for (const format of transformer.format) {
      if (!currentNode.hasFormat(format)) {
        currentNode.toggleFormat(format);
      }
    }
  }

  // Recursively run over inner text if it's not inline code
  if (!currentNode.hasFormat('code')) {
    importTextFormatTransformers(currentNode, textFormatTransformersIndex, textMatchTransformers);
  }

  // Run over leading/remaining text if any
  if (leadingNode) {
    importTextFormatTransformers(leadingNode, textFormatTransformersIndex, textMatchTransformers);
  }

  if (remainderNode) {
    importTextFormatTransformers(remainderNode, textFormatTransformersIndex, textMatchTransformers);
  }
}

function importTextMatchTransformers(textNode_: TextNode, textMatchTransformers: Array<TextMatchTransformer>) {
  let textNode = textNode_;

  mainLoop: while (textNode) {
    for (const transformer of textMatchTransformers) {
      const match = textNode.getTextContent().match(transformer.importRegExp);

      if (!match) {
        continue;
      }

      const startIndex = match.index || 0;
      const endIndex = startIndex + match[0].length;
      let replaceNode;
      let newTextNode;

      if (startIndex === 0) {
        [replaceNode, textNode] = textNode.splitText(endIndex);
      } else {
        [, replaceNode, newTextNode] = textNode.splitText(startIndex, endIndex);
      }

      if (newTextNode) {
        importTextMatchTransformers(newTextNode, textMatchTransformers);
      }
      transformer.replace(replaceNode, match);
      continue mainLoop;
    }

    break;
  }
}

// Finds first "<tag>content<tag>" match that is not nested into another tag
function findOutermostMatch(
  textContent: string,
  textTransformersIndex: TextFormatTransformersIndex,
): RegExpMatchArray | null {
  const openTagsMatch = textContent.match(textTransformersIndex.openTagsRegExp);

  if (openTagsMatch == null) {
    return null;
  }

  for (const match of openTagsMatch) {
    // Open tags reg exp might capture leading space so removing it
    // before using match to find transformer
    const tag = match.replace(/^\s/, '');
    const fullMatchRegExp = textTransformersIndex.fullMatchRegExpByTag[tag];
    if (fullMatchRegExp == null) {
      continue;
    }

    const fullMatch = textContent.match(fullMatchRegExp);
    const transformer = textTransformersIndex.transformersByTag[tag];
    if (fullMatch != null && transformer != null) {
      if (transformer.intraword !== false) {
        return fullMatch;
      }

      // For non-intraword transformers checking if it's within a word
      // or surrounded with space/punctuation/newline
      const { index = 0 } = fullMatch;
      const beforeChar = textContent[index - 1];
      const afterChar = textContent[index + fullMatch[0].length];

      if (
        (!beforeChar || PUNCTUATION_OR_SPACE.test(beforeChar)) &&
        (!afterChar || PUNCTUATION_OR_SPACE.test(afterChar))
      ) {
        return fullMatch;
      }
    }
  }

  return null;
}

function createTextFormatTransformersIndex(
  textTransformers: Array<TextFormatTransformer>,
): TextFormatTransformersIndex {
  const transformersByTag: Record<string, TextFormatTransformer> = {};
  const fullMatchRegExpByTag: Record<string, RegExp> = {};
  const openTagsRegExp = [];
  const escapeRegExp = `(?<![\\\\])`;

  for (const transformer of textTransformers) {
    const { tag } = transformer;
    transformersByTag[tag] = transformer;
    const tagRegExp = tag.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    openTagsRegExp.push(tagRegExp);

    if (IS_SAFARI || IS_IOS || IS_APPLE_WEBKIT) {
      fullMatchRegExpByTag[tag] = new RegExp(
        `(${tagRegExp})(?![${tagRegExp}\\s])(.*?[^${tagRegExp}\\s])${tagRegExp}(?!${tagRegExp})`,
      );
    } else {
      fullMatchRegExpByTag[tag] = new RegExp(
        `(?<![\\\\${tagRegExp}])(${tagRegExp})((\\\\${tagRegExp})?.*?[^${tagRegExp}\\s](\\\\${tagRegExp})?)((?<!\\\\)|(?<=\\\\\\\\))(${tagRegExp})(?![\\\\${tagRegExp}])`,
      );
    }
  }

  return {
    // Reg exp to find open tag + content + close tag
    fullMatchRegExpByTag,
    // Reg exp to find opening tags
    openTagsRegExp: new RegExp(
      `${IS_SAFARI || IS_IOS || IS_APPLE_WEBKIT ? '' : `${escapeRegExp}`}(${openTagsRegExp.join('|')})`,
      'g',
    ),
    transformersByTag,
  };
}
