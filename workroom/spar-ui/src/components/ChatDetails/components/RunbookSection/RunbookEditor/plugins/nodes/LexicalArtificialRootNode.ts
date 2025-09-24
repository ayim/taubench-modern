import {
  $getRoot,
  $isDecoratorNode,
  $isElementNode,
  $isTextNode,
  ElementNode,
  isCurrentlyReadOnlyMode,
  LexicalNode,
  SerializedElementNode,
  SerializedLexicalNode,
  TextNode,
} from 'lexical';
import invariant from '../lexical-markdown/MarkdownShortcuts';

export const cloneElementNode = (node: ElementNode) => {
  if (!$isElementNode(node)) {
    throw new Error('The provided node is not an ElementNode.');
  }

  // Create a new node of the same type
  const clonedNode = new node.constructor();

  // Copy over any relevant properties from the original node
  // eslint-disable-next-line no-underscore-dangle
  clonedNode.__key = node.__key;
  // eslint-disable-next-line no-underscore-dangle
  clonedNode.__type = node.__type;
  // eslint-disable-next-line no-underscore-dangle
  clonedNode.__format = node.__format;
  // eslint-disable-next-line no-underscore-dangle
  clonedNode.__style = node.__style;

  // Clone the children recursively
  node.getChildren().forEach((childNode) => {
    if ($isElementNode(childNode)) {
      const clonedChildNode = cloneElementNode(childNode);
      clonedNode.append(clonedChildNode);
    } else if ($isTextNode(childNode)) {
      const clonedChildNode = TextNode.clone(childNode);
      clonedNode.append(clonedChildNode);
    }
  });

  return clonedNode;
};

export type SerializedRootNode<T extends SerializedLexicalNode = SerializedLexicalNode> = SerializedElementNode<T>;

export class ArtificialRootNode extends ElementNode {
  // eslint-disable-next-line no-underscore-dangle
  __cachedText: null | string;

  static getType(): string {
    return 'artificial-root';
  }

  static clone(): ArtificialRootNode {
    return new ArtificialRootNode();
  }

  constructor() {
    super();
    // eslint-disable-next-line no-underscore-dangle
    this.__cachedText = null;
  }

  // eslint-disable-next-line class-methods-use-this
  getTopLevelElementOrThrow(): never {
    invariant(false, 'getTopLevelElementOrThrow: root nodes are not top level elements');
  }

  getTextContent(): string {
    // eslint-disable-next-line no-underscore-dangle
    const cachedText = this.__cachedText;
    if (isCurrentlyReadOnlyMode()) {
      if (cachedText !== null) {
        return cachedText;
      }
    }
    return super.getTextContent();
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars, class-methods-use-this
  replace<N = LexicalNode>(_node: N): never {
    invariant(false, 'replace: cannot be called on root nodes');
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars, class-methods-use-this
  insertBefore(_nodeToInsert: LexicalNode): LexicalNode {
    invariant(false, 'insertBefore: cannot be called on root nodes');
  }

  // eslint-disable-next-line @typescript-eslint/no-unused-vars, class-methods-use-this
  insertAfter(_nodeToInsert: LexicalNode): LexicalNode {
    invariant(false, 'insertAfter: cannot be called on root nodes');
  }

  // View
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, class-methods-use-this
  updateDOM(_prevNode: ArtificialRootNode, _dom: HTMLElement): false {
    return false;
  }

  // Mutate
  append(...nodesToAppend: LexicalNode[]): this {
    nodesToAppend.forEach((node) => {
      if (!$isElementNode(node) && !$isDecoratorNode(node)) {
        invariant(false, 'rootNode.append: Only element or decorator nodes can be appended to the root node');
      }
    });
    return super.append(...nodesToAppend);
  }

  static importJSON(serializedNode: SerializedRootNode): ArtificialRootNode {
    // We don't create a root, and instead use the existing root.
    const node = $getRoot();
    node.setFormat(serializedNode.format);
    node.setIndent(serializedNode.indent);
    node.setDirection(serializedNode.direction);
    return node;
  }

  exportJSON(): SerializedRootNode {
    return {
      children: [],
      direction: this.getDirection(),
      format: this.getFormatType(),
      indent: this.getIndent(),
      type: 'artificial-root',
      version: 1,
    };
  }

  // eslint-disable-next-line class-methods-use-this
  collapseAtStart(): true {
    return true;
  }
}

export function $createArtificialRootNode(): ArtificialRootNode {
  return new ArtificialRootNode();
}

export function $isArtificialRootNode(
  node: ArtificialRootNode | LexicalNode | null | undefined,
): node is ArtificialRootNode {
  return node instanceof ArtificialRootNode;
}
