import {
  ELEMENT_TRANSFORMERS,
  ElementTransformer,
  HEADING,
  INLINE_CODE,
  ORDERED_LIST,
  QUOTE,
  TEXT_FORMAT_TRANSFORMERS,
  Transformer,
  UNORDERED_LIST,
} from '@lexical/markdown';
import {
  $createHorizontalRuleNode,
  $isHorizontalRuleNode,
  HorizontalRuleNode,
} from '@lexical/react/LexicalHorizontalRuleNode';

import { LexicalNode } from 'lexical';
import { CODE, LINK } from '../plugins/lexical-markdown';

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

export const MARKDOWN_TRANSFORMERS: Array<Transformer> = [
  HR,
  HEADING,
  QUOTE,
  LINK,
  INLINE_CODE,
  ORDERED_LIST,
  UNORDERED_LIST,
  CODE,
  ...ELEMENT_TRANSFORMERS,
  ...TEXT_FORMAT_TRANSFORMERS,
];
