/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable class-methods-use-this */
/* eslint-disable no-underscore-dangle */
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
} from 'lexical';
import invariant from '../lexical-markdown/MarkdownShortcuts';

export const cloneElementNode = (node: ElementNode): ElementNode => {
  if (!$isElementNode(node)) {
    throw new Error('The provided node is not an ElementNode.');
  }

  // Create a new node of the same type (Lexical will auto-generate a unique key)
  const clonedNode = node.constructor.clone(node) as ElementNode;

  // Clone the children recursively
  node.getChildren().forEach((childNode) => {
    if ($isElementNode(childNode)) {
      const clonedChildNode = cloneElementNode(childNode);
      clonedNode.append(clonedChildNode);
    } else if ($isTextNode(childNode)) {
      const clonedChildNode = childNode.constructor.clone(childNode) as LexicalNode;
      clonedNode.append(clonedChildNode);
    } else if ($isDecoratorNode(childNode)) {
      const clonedChildNode = childNode.constructor.clone(childNode) as LexicalNode;
      clonedNode.append(clonedChildNode);
    }
  });

  return clonedNode;
};

export type SerializedRootNode<T extends SerializedLexicalNode = SerializedLexicalNode> = SerializedElementNode<T>;

export class ArtificialRootNode extends ElementNode {
  __cachedText: null | string;

  static getType(): string {
    return 'artificial-root';
  }

  static clone(): ArtificialRootNode {
    return new ArtificialRootNode();
  }

  constructor() {
    super();
    this.__cachedText = null;
  }

  getTopLevelElementOrThrow(): never {
    invariant(false, 'getTopLevelElementOrThrow: root nodes are not top level elements');
  }

  getTextContent(): string {
    const cachedText = this.__cachedText;
    if (isCurrentlyReadOnlyMode()) {
      if (cachedText !== null) {
        return cachedText;
      }
    }
    return super.getTextContent();
  }

  replace<N = LexicalNode>(_node: N): never {
    invariant(false, 'replace: cannot be called on root nodes');
  }

  insertBefore(_nodeToInsert: LexicalNode): LexicalNode {
    invariant(false, 'insertBefore: cannot be called on root nodes');
  }

  insertAfter(_nodeToInsert: LexicalNode): LexicalNode {
    invariant(false, 'insertAfter: cannot be called on root nodes');
  }

  // View

  updateDOM(_prevNode: ArtificialRootNode, _dom: HTMLElement): false {
    return false;
  }

  // Mutate

  append(...nodesToAppend: LexicalNode[]): this {
    for (let i = 0; i < nodesToAppend.length; i += 1) {
      const node = nodesToAppend[i];
      if (!$isElementNode(node) && !$isDecoratorNode(node)) {
        invariant(false, 'rootNode.append: Only element or decorator nodes can be appended to the root node');
      }
    }
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
