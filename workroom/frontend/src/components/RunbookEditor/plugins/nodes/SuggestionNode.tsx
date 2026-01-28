/* eslint-disable react/no-danger */
/* eslint-disable no-restricted-syntax */
/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable class-methods-use-this */
/* eslint-disable no-underscore-dangle */

import { JSX, useEffect, useRef } from 'react';
import {
  $getSelection,
  $isRangeSelection,
  $createTextNode,
  DecoratorNode,
  EditorConfig,
  LexicalEditor,
  LexicalNode,
  NodeKey,
  SerializedLexicalNode,
  Spread,
  ElementNode,
  $isRootNode,
} from 'lexical';
import { Badge } from '@sema4ai/components';
import { IconCheck, IconClose } from '@sema4ai/icons';
import { marked } from 'marked';
import { $isListItemNode, $isListNode } from '@lexical/list';
import { MARKDOWN_TRANSFORMERS } from '../lexical-markdown/MarkdownTransformers';
import { $convertFromMarkdownString } from '../lexical-markdown';
import { $createArtificialRootNode } from './LexicalArtificialRootNode';
import { findAppropriateAncestorToReplace } from '../lexical-utils';

export interface OriginalNode {
  textContent: string;
  key: NodeKey;
  parent: LexicalNode | null;
  prev: LexicalNode | null;
  next: LexicalNode | null;
  type: string;
}

export interface SuggestionPayload {
  originalNode: LexicalNode | null;
  newMarkdownText: string;
  isAddition?: boolean;
  isRemoval?: boolean;
  key?: NodeKey;
  originalTextOverride?: string; // Override for original text when matching at parent level
}

export type SerializedOriginalNode = {
  textContent: string;
  key: NodeKey;
  type: string;
};

export type SerializedSuggestionNode = Spread<
  {
    originalNode: SerializedOriginalNode;
    newMarkdownText: string;
  },
  SerializedLexicalNode
>;

const SuggestionComponent = ({
  originalText,
  newText,
  onAccept,
  onReject,
}: {
  originalText: string;
  newText: string;
  onAccept: () => void;
  onReject: () => void;
}): JSX.Element => {
  const componentRef = useRef<HTMLSpanElement>(null);

  // Trim leading/trailing whitespace to prevent markdown from treating indented text as code blocks
  const trimmedNewText = newText.trim();

  const newTextAsHTML = (marked.parse(trimmedNewText, { async: false, gfm: false, breaks: false }) as string)
    .replace(/>\s+</g, '><') // Remove whitespace between tags
    .replace(/^<p>([\s\S]*)<\/p>$/, '$1') // Remove wrapping <p> tags (avoid unsupported /s flag)
    .trim();

  // CSS to ensure all nested elements respect boundaries
  const constraintStyles = `
    .suggestion-node-content * {
      max-width: 100%;
      box-sizing: border-box;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
    .suggestion-node-content img {
      max-width: 100%;
      height: auto;
    }
    .suggestion-node-content pre,
    .suggestion-node-content code {
      white-space: pre-wrap;
      word-break: break-word;
      overflow-wrap: anywhere;
    }
  `;

  useEffect(() => {
    if (componentRef.current) {
      componentRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'nearest',
        inline: 'nearest',
      });
    }
  }, []);

  return (
    <>
      <style>{constraintStyles}</style>
      <span
        ref={componentRef}
        contentEditable={false}
        data-lexical-decorator="true"
        style={{
          display: 'inline-block',
          maxWidth: '100%',
          width: '100%',
          margin: '4px 0',
          verticalAlign: 'top',
          boxSizing: 'border-box',
        }}
      >
        <span
          style={{
            display: 'block',
            width: '100%',
            boxSizing: 'border-box',
          }}
        >
          {/* Original text with light red background */}
          {!!originalText && (
            <span
              className="suggestion-node-content"
              style={{
                display: 'block',
                backgroundColor: 'rgba(var(--color-background-error-light))',
                padding: '4px',
                marginBottom: newText ? '4px' : '0',
                boxSizing: 'border-box',
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
                hyphens: 'auto',
              }}
            >
              {originalText}
            </span>
          )}

          {/* New text with green background */}
          {!!newText && (
            <span
              className="suggestion-node-content"
              style={{
                display: 'block',
                backgroundColor: 'rgba(var(--color-background-success-light))',
                padding: '4px',
                marginBottom: '4px',
                boxSizing: 'border-box',
                wordBreak: 'break-word',
                overflowWrap: 'anywhere',
                hyphens: 'auto',
              }}
              dangerouslySetInnerHTML={{ __html: newTextAsHTML }}
            />
          )}

          {/* Action buttons */}
          <span
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '4px',
              width: '100%',
              boxSizing: 'border-box',
            }}
          >
            <Badge
              aria-label="Accept change"
              forwardedAs="button"
              icon={IconCheck}
              iconVisible
              iconColor="content.success"
              variant="success"
              size="small"
              style={{ borderRadius: '0px', border: '0px', flexShrink: 0 }}
              onClick={onAccept}
              label="Keep"
            />
            <Badge
              aria-label="Reject change"
              forwardedAs="button"
              icon={IconClose}
              iconVisible
              iconColor="content.error"
              variant="danger"
              size="small"
              style={{ borderRadius: '0px', border: '0px', flexShrink: 0 }}
              onClick={onReject}
              label="Reject"
            />
          </span>
        </span>
      </span>
    </>
  );
};

export class SuggestionNode extends DecoratorNode<JSX.Element> {
  __originalNode: OriginalNode | null;

  __newMarkdownText: string;

  __isAddition?: boolean;

  __isRemoval?: boolean;

  static getType(): string {
    return 'suggestion';
  }

  constructor(
    originalNode: LexicalNode | null,
    newMarkdownText: string,
    isAddition?: boolean,
    isRemoval?: boolean,
    key?: NodeKey,
    originalTextOverride?: string,
  ) {
    super(key);
    this.__originalNode = {
      textContent: originalTextOverride ?? originalNode?.getTextContent() ?? '',
      key: originalNode?.getKey() ?? '',
      parent: originalNode?.getParent() ?? null,
      prev: originalNode?.getPreviousSibling() ?? null,
      next: originalNode?.getNextSibling() ?? null,
      type: originalNode?.getType() ?? '',
    };
    this.__newMarkdownText = newMarkdownText;
    this.__isAddition = isAddition ?? false;
    this.__isRemoval = isRemoval ?? false;
  }

  createDOM(): HTMLElement {
    const span = document.createElement('span');
    span.className = 'suggestion-node-wrapper';
    span.style.display = 'inline-block';
    span.style.maxWidth = '100%';
    span.style.width = '100%';
    span.style.verticalAlign = 'top';
    span.style.boxSizing = 'border-box';
    span.setAttribute('data-lexical-suggestion', 'true');
    span.setAttribute('contenteditable', 'false');
    return span;
  }

  updateDOM(_prevNode: SuggestionNode, _dom: HTMLElement): boolean {
    // Text changes don't require DOM updates for DecoratorNodes
    // The React component will handle text changes
    return false;
  }

  getOriginalText(): string {
    return this.__originalNode?.textContent ?? '';
  }

  getNewText(): string {
    return this.__newMarkdownText;
  }

  getOriginalParent(): LexicalNode | null {
    return this.__originalNode?.parent ?? null;
  }

  setOriginalNode(node: OriginalNode | null): void {
    const writable = this.getWritable();
    writable.__originalNode = node;
  }

  setNewMarkdownText(markdownText: string): void {
    const writable = this.getWritable();
    writable.__newMarkdownText = markdownText;
  }

  getTextContent(): string {
    // Return the new text as the text content for selection/copy purposes
    return this.__newMarkdownText;
  }

  /**
   * Handles accepting an addition suggestion
   */
  private handleAdditionAcceptance(): void {
    // Create an empty paragraph node
    const artificialRootNode = $createArtificialRootNode();
    // Convert the new text from markdown to lexical nodes & inject them into the paragraph node
    $convertFromMarkdownString(this.__newMarkdownText, MARKDOWN_TRANSFORMERS, artificialRootNode as ElementNode, true);

    // All children of the artificial root node should be inserted into the editor
    // eslint-disable-next-line @typescript-eslint/no-this-alias
    let insertAfterNode: LexicalNode | null = this;
    for (const child of artificialRootNode.getChildren()) {
      // Insert the entire node (including lists with their items)
      const theParent = insertAfterNode.getParent();
      if (theParent && !$isRootNode(theParent)) {
        theParent.insertAfter(child);
      } else {
        insertAfterNode.insertAfter(child);
      }
      insertAfterNode = child;
    }

    // Remove the suggestion node
    this.remove();
  }

  /**
   * Handles accepting a removal suggestion
   */
  private handleRemovalAcceptance(): void {
    // Create an empty text node
    const textNode = $createTextNode('');

    // Replace this suggestion node with the empty text node
    this.replace(textNode);

    // We should delete the parent node if it is not the root node & it is empty
    const parent = this.getOriginalParent();
    if (parent && !$isRootNode(parent) && parent.getTextContent().trim() === '') {
      parent.remove();
    }
  }

  /**
   * Handles accepting a replacement/improvement suggestion
   */
  private handleReplacementAcceptance(): void {
    // Convert the new markdown text to Lexical nodes
    const artificialRootNode = $createArtificialRootNode();
    $convertFromMarkdownString(this.__newMarkdownText, MARKDOWN_TRANSFORMERS, artificialRootNode as ElementNode, true);

    const newNodes = artificialRootNode.getChildren();

    // Find the appropriate ancestor block to replace based on the new node types
    // This ensures we replace at the right level (e.g., quote with quote, not the whole tree)
    const { ancestor: ancestorBlock, nodesToInsert } = findAppropriateAncestorToReplace(this, newNodes);

    // If we have an ancestor block and nodes to insert
    if (ancestorBlock && nodesToInsert.length > 0) {
      this.replaceAncestorWithNodes(ancestorBlock, nodesToInsert);
    } else {
      this.fallbackToTextReplacement();
    }
  }

  /**
   * Replaces an ancestor block with new nodes, preserving nested children if needed
   */
  private replaceAncestorWithNodes(ancestorBlock: LexicalNode, nodesToInsert: LexicalNode[]): void {
    // First, detach all nodes from their current parents to ensure clean insertion
    // This is important because nodes from artificialRootNode might still be attached
    nodesToInsert.forEach((node) => {
      try {
        node.remove();
      } catch (e) {
        // Node might not be attached, that's fine
      }
    });

    // Special handling for list items: preserve nested children
    let nestedChildren: LexicalNode[] = [];
    if ($isListItemNode(ancestorBlock)) {
      // Extract nested list children (nested lists) before replacing
      const children = ancestorBlock.getChildren();
      nestedChildren = children.filter((child) => $isListNode(child));
    }

    // Replace the entire ancestor block with the new nodes

    let insertAfterNode: LexicalNode | null = ancestorBlock;

    // Insert all nodes after the ancestor block
    for (const newNode of nodesToInsert) {
      insertAfterNode.insertAfter(newNode);

      // If this is a list item and we have nested children to preserve, append them
      if ($isListItemNode(newNode) && nestedChildren.length > 0) {
        nestedChildren.forEach((nestedChild) => {
          try {
            // Remove from old location first
            nestedChild.remove();
          } catch (e) {
            // Might already be removed
          }
          newNode.append(nestedChild);
        });
      }

      insertAfterNode = newNode;
    }

    // Remove the old ancestor block (this will also remove the suggestion node)
    ancestorBlock.remove();
  }

  /**
   * Fallback method: replaces the suggestion node with a simple text node
   */
  private fallbackToTextReplacement(): void {
    const textNode = $createTextNode(this.__newMarkdownText);
    this.replace(textNode);

    // Position cursor after the newly inserted text
    const selection = $getSelection();
    if ($isRangeSelection(selection)) {
      selection.anchor.set(textNode.getKey(), this.__newMarkdownText.length, 'text');
      selection.focus.set(textNode.getKey(), this.__newMarkdownText.length, 'text');
    }
  }

  /**
   * Accept the suggestion - replaces the node with the new text
   * Can be called from external entities
   */
  acceptSuggestion(editor: LexicalEditor): void {
    // Preserve scroll position before update
    const editorContainer = editor.getRootElement();
    const scrollTop = editorContainer?.scrollTop || 0;
    const scrollLeft = editorContainer?.scrollLeft || 0;

    editor.update(() => {
      if (this.__isAddition) {
        this.handleAdditionAcceptance();
      } else if (this.__isRemoval) {
        this.handleRemovalAcceptance();
      } else {
        this.handleReplacementAcceptance();
      }
    });

    // Restore scroll position after update completes and DOM is updated
    if (editorContainer) {
      requestAnimationFrame(() => {
        editorContainer.scrollTop = scrollTop;
        editorContainer.scrollLeft = scrollLeft;
      });
    }
  }

  /**
   * Handles rejecting an addition suggestion
   */
  private handleAdditionRejection(): void {
    this.remove();
  }

  /**
   * Handles rejecting a removal suggestion
   */
  private handleRemovalRejection(): void {
    // Create a text node with the original content
    const textNode = $createTextNode(this.__originalNode?.textContent ?? '');
    // Replace this suggestion node with the original text node
    this.replace(textNode);
  }

  /**
   * Handles rejecting a replacement suggestion
   */
  private handleReplacementRejection(): void {
    // Create a text node with the original text
    const textNode = $createTextNode(this.__originalNode?.textContent ?? '');

    // Replace this suggestion node with the original text node
    this.replace(textNode);

    // Position cursor after the inserted text
    const selection = $getSelection();
    if ($isRangeSelection(selection)) {
      selection.anchor.set(textNode.getKey(), this.__originalNode?.textContent?.length ?? 0, 'text');
      selection.focus.set(textNode.getKey(), this.__originalNode?.textContent?.length ?? 0, 'text');
    }
  }

  /**
   * Reject the suggestion - replaces the node with the original text
   * Can be called from external entities
   */
  rejectSuggestion(editor: LexicalEditor): void {
    // Preserve scroll position before update
    const editorContainer = editor.getRootElement();
    const scrollTop = editorContainer?.scrollTop || 0;
    const scrollLeft = editorContainer?.scrollLeft || 0;

    editor.update(() => {
      if (this.__isAddition) {
        this.handleAdditionRejection();
      } else if (this.__isRemoval) {
        this.handleRemovalRejection();
      } else {
        this.handleReplacementRejection();
      }
    });

    // Restore scroll position after update completes and DOM is updated
    if (editorContainer) {
      requestAnimationFrame(() => {
        editorContainer.scrollTop = scrollTop;
        editorContainer.scrollLeft = scrollLeft;
      });
    }
  }

  decorate(editor: LexicalEditor, _config: EditorConfig): JSX.Element {
    const handleAccept = () => {
      this.acceptSuggestion(editor);
    };

    const handleReject = () => {
      this.rejectSuggestion(editor);
    };

    return (
      <SuggestionComponent
        originalText={this.__originalNode?.textContent ?? ''}
        newText={this.__newMarkdownText}
        onAccept={handleAccept}
        onReject={handleReject}
      />
    );
  }

  isInline(): boolean {
    return false;
  }

  isKeyboardSelectable(): boolean {
    return false;
  }

  static clone(node: SuggestionNode): SuggestionNode {
    const clonedNode = new SuggestionNode(
      null,
      node.__newMarkdownText,
      node.__isAddition,
      node.__isRemoval,
      node.__key,
    );
    clonedNode.__originalNode = node.__originalNode;
    return clonedNode;
  }

  exportJSON(): SerializedSuggestionNode {
    return {
      originalNode: {
        textContent: this.__originalNode?.textContent ?? '',
        key: this.__originalNode?.key ?? '',
        type: this.__originalNode?.type ?? '',
      },
      newMarkdownText: this.__newMarkdownText,
      type: 'suggestion',
      version: 1,
    };
  }

  static importJSON(serializedNode: SerializedSuggestionNode): SuggestionNode {
    const node = new SuggestionNode(null, serializedNode.newMarkdownText);
    // Restore the serializable fields from the original node
    node.__originalNode = {
      textContent: serializedNode.originalNode?.textContent ?? '',
      key: serializedNode.originalNode?.key ?? '',
      type: serializedNode.originalNode?.type ?? '',
      parent: null,
      prev: null,
      next: null,
    };
    return node;
  }
}

export function $createSuggestionNode(payload: SuggestionPayload): SuggestionNode {
  const { originalNode, newMarkdownText: newText, isAddition, isRemoval, key, originalTextOverride } = payload;
  const node = new SuggestionNode(
    originalNode,
    newText,
    isAddition ?? false,
    isRemoval ?? false,
    key,
    originalTextOverride,
  );
  return node;
}

export function $isSuggestionNode(node: LexicalNode | null | undefined): node is SuggestionNode {
  const result = node instanceof SuggestionNode;
  return result;
}
