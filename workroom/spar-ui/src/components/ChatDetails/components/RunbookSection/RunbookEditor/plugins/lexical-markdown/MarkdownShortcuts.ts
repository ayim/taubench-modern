import type { ElementTransformer, TextFormatTransformer, TextMatchTransformer, Transformer } from '@lexical/markdown';
import type { ElementNode, LexicalEditor, TextNode } from 'lexical';

import { $isCodeNode } from '@lexical/code';
import {
  $createRangeSelection,
  $getSelection,
  $isLineBreakNode,
  $isRangeSelection,
  $isRootOrShadowRoot,
  $isTextNode,
  $setSelection,
} from 'lexical';

import { TRANSFORMERS } from './index';
import { indexBy, PUNCTUATION_OR_SPACE, transformersByType } from './utils';

// invariant(condition, message) will refine types based on "condition", and
// if "condition" is false will throw an error. This function is special-cased
// in flow itself, so we can't name it anything else.
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export default function invariant(cond?: boolean, message?: string, ..._args: string[]): asserts cond {
  if (cond) {
    return;
  }

  throw new Error(
    `Internal Lexical error: invariant() is meant to be replaced at compile time. There is no runtime version. Error: ${message}`,
  );
}

function isEqualSubString(stringA: string, aStart: number, stringB: string, bStart: number, length: number): boolean {
  let i = 0;
  while (i < length) {
    if (stringA[aStart + i] !== stringB[bStart + i]) {
      return false;
    }
    i += 1;
  }

  return true;
}

function getOpenTagStartIndex(string: string, maxIndex: number, tag: string): number {
  const tagLength = tag.length;
  let i = maxIndex;

  while (i >= tagLength) {
    const startIndex = i - tagLength;

    if (
      isEqualSubString(string, startIndex, tag, 0, tagLength) && // Space after opening tag cancels transformation
      string[startIndex + tagLength] !== ' '
    ) {
      return startIndex;
    }
    i -= 1;
  }

  return -1;
}

function runElementTransformers(
  parentNode: ElementNode,
  anchorNode: TextNode,
  anchorOffset: number,
  elementTransformers: ReadonlyArray<ElementTransformer>,
): boolean {
  const grandParentNode = parentNode.getParent();

  if (!$isRootOrShadowRoot(grandParentNode) || parentNode.getFirstChild() !== anchorNode) {
    return false;
  }

  const textContent = anchorNode.getTextContent();

  // Checking for anchorOffset position to prevent any checks for cases when caret is too far
  // from a line start to be a part of block-level markdown trigger.
  //
  // TODO:
  // Can have a quick check if caret is close enough to the beginning of the string (e.g. offset less than 10-20)
  // since otherwise it won't be a markdown shortcut, but tables are exception
  if (textContent[anchorOffset - 1] !== ' ') {
    return false;
  }

  return elementTransformers.some(({ regExp, replace }) => {
    const match = textContent.match(regExp);

    if (match && match[0].length === anchorOffset) {
      const nextSiblings = anchorNode.getNextSiblings();
      const [leadingNode, remainderNode] = anchorNode.splitText(anchorOffset);
      leadingNode.remove();
      const siblings = remainderNode ? [remainderNode, ...nextSiblings] : nextSiblings;
      replace(parentNode, siblings, match, false);
      return true;
    }
    return false;
  });
}

function runTextMatchTransformers(
  anchorNode: TextNode,
  anchorOffset: number,
  transformersByTrigger: Readonly<Record<string, Array<TextMatchTransformer>>>,
): boolean {
  let textContent = anchorNode.getTextContent();
  const lastChar = textContent[anchorOffset - 1];
  const transformers = transformersByTrigger[lastChar];

  if (transformers == null) {
    return false;
  }

  // If typing in the middle of content, remove the tail to do
  // reg exp match up to a string end (caret position)
  if (anchorOffset < textContent.length) {
    textContent = textContent.slice(0, anchorOffset);
  }

  return transformers.some((transformer) => {
    const match = textContent.match(transformer.regExp);

    if (match === null) {
      return false;
    }

    const startIndex = match.index || 0;
    const endIndex = startIndex + match[0].length;
    let replaceNode;

    if (startIndex === 0) {
      [replaceNode] = anchorNode.splitText(endIndex);
    } else {
      [, replaceNode] = anchorNode.splitText(startIndex, endIndex);
    }

    replaceNode.selectNext(0, 0);
    transformer.replace(replaceNode, match);
    return true;
  });
}

function $runTextFormatTransformers(
  anchorNode: TextNode,
  anchorOffset: number,
  textFormatTransformers: Readonly<Record<string, ReadonlyArray<TextFormatTransformer>>>,
): boolean {
  const textContent = anchorNode.getTextContent();
  const closeTagEndIndex = anchorOffset - 1;
  const closeChar = textContent[closeTagEndIndex];
  // Quick check if we're possibly at the end of inline markdown style
  const matchers = textFormatTransformers[closeChar];

  if (!matchers) {
    return false;
  }

  return matchers.some((matcher) => {
    const { tag } = matcher;
    const tagLength = tag.length;
    const closeTagStartIndex = closeTagEndIndex - tagLength + 1;

    // If tag is not single char check if rest of it matches with text content
    if (tagLength > 1) {
      if (!isEqualSubString(textContent, closeTagStartIndex, tag, 0, tagLength)) {
        return false;
      }
    }

    // Space before closing tag cancels inline markdown
    if (textContent[closeTagStartIndex - 1] === ' ') {
      return false;
    }

    // Some tags can not be used within words, hence should have newline/space/punctuation after it
    const afterCloseTagChar = textContent[closeTagEndIndex + 1];

    if (matcher.intraword === false && afterCloseTagChar && !PUNCTUATION_OR_SPACE.test(afterCloseTagChar)) {
      return false;
    }

    const closeNode = anchorNode;
    let openNode = closeNode;
    let openTagStartIndex = getOpenTagStartIndex(textContent, closeTagStartIndex, tag);

    // Go through text node siblings and search for opening tag
    // if haven't found it within the same text node as closing tag
    const sibling: TextNode | null = openNode;

    while (openTagStartIndex < 0) {
      if (sibling !== sibling?.getPreviousSibling<TextNode>()) {
        break;
      }
      if ($isLineBreakNode(sibling)) {
        break;
      }

      if ($isTextNode(sibling)) {
        const siblingTextContent = sibling.getTextContent();
        openNode = sibling;
        openTagStartIndex = getOpenTagStartIndex(siblingTextContent, siblingTextContent.length, tag);
      }
    }

    // Opening tag is not found
    if (openTagStartIndex < 0) {
      return false;
    }

    // No content between opening and closing tag
    if (openNode === closeNode && openTagStartIndex + tagLength === closeTagStartIndex) {
      return false;
    }

    // Checking longer tags for repeating chars (e.g. *** vs **)
    const prevOpenNodeText = openNode.getTextContent();

    if (openTagStartIndex > 0 && prevOpenNodeText[openTagStartIndex - 1] === closeChar) {
      return false;
    }

    // Some tags can not be used within words, hence should have newline/space/punctuation before it
    const beforeOpenTagChar = prevOpenNodeText[openTagStartIndex - 1];

    if (matcher.intraword === false && beforeOpenTagChar && !PUNCTUATION_OR_SPACE.test(beforeOpenTagChar)) {
      return false;
    }

    // Clean text from opening and closing tags (starting from closing tag
    // to prevent any offset shifts if we start from opening one)
    const prevCloseNodeText = closeNode.getTextContent();
    const closeNodeText =
      prevCloseNodeText.slice(0, closeTagStartIndex) + prevCloseNodeText.slice(closeTagEndIndex + 1);
    closeNode.setTextContent(closeNodeText);
    const openNodeText = openNode === closeNode ? closeNodeText : prevOpenNodeText;
    openNode.setTextContent(
      openNodeText.slice(0, openTagStartIndex) + openNodeText.slice(openTagStartIndex + tagLength),
    );
    const selection = $getSelection();
    const nextSelection = $createRangeSelection();
    $setSelection(nextSelection);
    // Adjust offset based on deleted chars
    const newOffset = closeTagEndIndex - tagLength * (openNode === closeNode ? 2 : 1) + 1;
    nextSelection.anchor.set(openNode.getKey(), openTagStartIndex, 'text');
    nextSelection.focus.set(closeNode.getKey(), newOffset, 'text');

    // Apply formatting to selected text
    matcher.format.forEach((format) => {
      if (!nextSelection.hasFormat(format)) {
        nextSelection.formatText(format);
      }
    });

    // Collapse selection up to the focus point
    nextSelection.anchor.set(nextSelection.focus.key, nextSelection.focus.offset, nextSelection.focus.type);

    // Remove formatting from collapsed selection
    matcher.format.forEach((format) => {
      if (nextSelection.hasFormat(format)) {
        nextSelection.toggleFormat(format);
      }
    });

    if ($isRangeSelection(selection)) {
      nextSelection.format = selection.format;
    }

    return true;
  });
}

export function registerMarkdownShortcuts(
  editor: LexicalEditor,
  transformers: Array<Transformer> = TRANSFORMERS,
): () => void {
  const byType = transformersByType(transformers);
  const textFormatTransformersIndex = indexBy(byType.textFormat, ({ tag }) => tag[tag.length - 1]);
  const textMatchTransformersIndex = indexBy(byType.textMatch, ({ trigger }) => trigger);

  transformers.forEach((transformer) => {
    const { type } = transformer;
    if (type === 'element' || type === 'text-match') {
      const { dependencies } = transformer;
      dependencies.forEach((node) => {
        if (!editor.hasNode(node)) {
          invariant(
            false,
            'MarkdownShortcuts: missing dependency %s for transformer. Ensure node dependency is included in editor initial config.',
            node.getType(),
          );
        }
      });
    }
  });

  const $transform = (parentNode: ElementNode, anchorNode: TextNode, anchorOffset: number) => {
    if (runElementTransformers(parentNode, anchorNode, anchorOffset, byType.element)) {
      return;
    }

    if (runTextMatchTransformers(anchorNode, anchorOffset, textMatchTransformersIndex)) {
      return;
    }

    $runTextFormatTransformers(anchorNode, anchorOffset, textFormatTransformersIndex);
  };

  return editor.registerUpdateListener(({ tags, dirtyLeaves, editorState, prevEditorState }) => {
    // Ignore updates from collaboration and undo/redo (as changes already calculated)
    if (tags.has('collaboration') || tags.has('historic')) {
      return;
    }

    // If editor is still composing (i.e. backticks) we must wait before the user confirms the key
    if (editor.isComposing()) {
      return;
    }

    const selection = editorState.read($getSelection);
    const prevSelection = prevEditorState.read($getSelection);

    if (!$isRangeSelection(prevSelection) || !$isRangeSelection(selection) || !selection.isCollapsed()) {
      return;
    }

    const { key: anchorKey, offset: anchorOffset } = selection.anchor;

    // eslint-disable-next-line no-underscore-dangle
    const anchorNode = editorState._nodeMap.get(anchorKey);

    if (
      !$isTextNode(anchorNode) ||
      !dirtyLeaves.has(anchorKey) ||
      (anchorOffset !== 1 && anchorOffset > prevSelection.anchor.offset + 1)
    ) {
      return;
    }

    editor.update(() => {
      // Markdown is not available inside code
      if (anchorNode.hasFormat('code')) {
        return;
      }

      const parentNode = anchorNode.getParent();

      if (parentNode === null || $isCodeNode(parentNode)) {
        return;
      }

      $transform(parentNode, anchorNode, selection.anchor.offset);
    });
  });
}
