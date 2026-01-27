/* eslint-disable class-methods-use-this */
/* eslint-disable @typescript-eslint/no-use-before-define */
import {
  EditorConfig,
  TextNode,
  type SerializedTextNode,
  $getSelection,
  $isRangeSelection,
  $isTextNode,
  LexicalNode,
  LexicalEditor,
} from 'lexical';

export const MATCH_COLOR = 'yellow';
export const CURRENT_MATCH_COLOR = 'orange';

export type SerializedHighlightNode = SerializedTextNode & {
  type: 'highlight';
  version: 1;
};

export class HighlightNode extends TextNode {
  static getType(): string {
    return 'highlight';
  }

  static clone(node: HighlightNode): HighlightNode {
    return new HighlightNode(node.__text, node.__key); // eslint-disable-line no-underscore-dangle
  }

  createDOM(config: EditorConfig): HTMLElement {
    const element = super.createDOM(config);
    element.style.backgroundColor = MATCH_COLOR;
    return element;
  }

  exportJSON(): SerializedHighlightNode {
    return {
      ...super.exportJSON(),
      type: 'highlight',
      version: 1,
    };
  }

  static importJSON(serializedNode: SerializedHighlightNode): HighlightNode {
    const node = $createHighlightNode(serializedNode.text); // eslint-disable-line no-use-before-define
    node.setFormat(serializedNode.format);
    node.setDetail(serializedNode.detail);
    node.setMode(serializedNode.mode);
    node.setStyle(serializedNode.style);
    return node;
  }

  setBackgroundColor(editor: LexicalEditor, key: string, color: string): void {
    const domElement = editor.getElementByKey(key);
    if (domElement) {
      domElement.style.backgroundColor = color;
    }
  }
}

export function $createHighlightNode(text: string): HighlightNode {
  const node = new HighlightNode(text);

  // If we're creating this from an existing text node, preserve its format
  const selection = $getSelection();
  if ($isRangeSelection(selection)) {
    const { anchor } = selection;
    const anchorNode = anchor.getNode();
    if ($isTextNode(anchorNode)) {
      node.setFormat(anchorNode.getFormat());
      node.setStyle(anchorNode.getStyle());
      node.setMode(anchorNode.getMode());
      node.setDetail(anchorNode.getDetail());
    }
  }

  return node;
}

export function $isHighlightNode(node: LexicalNode): node is HighlightNode {
  return node instanceof HighlightNode;
}
