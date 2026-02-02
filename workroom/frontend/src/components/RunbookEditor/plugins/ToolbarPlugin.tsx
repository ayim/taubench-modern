/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck
import { useCallback, useEffect, useRef, useState } from 'react';

import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $findMatchingParent, mergeRegister } from '@lexical/utils';
import {
  $createParagraphNode,
  $getSelection,
  $isRangeSelection,
  $isRootOrShadowRoot,
  CAN_REDO_COMMAND,
  CAN_UNDO_COMMAND,
  FORMAT_TEXT_COMMAND,
  INDENT_CONTENT_COMMAND,
  OUTDENT_CONTENT_COMMAND,
  REDO_COMMAND,
  SELECTION_CHANGE_COMMAND,
  UNDO_COMMAND,
} from 'lexical';
import { Box, Button, Select, Tooltip } from '@sema4ai/components';
import {
  IconBlockquote,
  IconBold,
  IconCode,
  IconCode3,
  IconDbTable,
  IconFileScan,
  IconHeading,
  IconIndentLeft,
  IconIndentRight,
  IconItalic,
  IconLink,
  IconNumberedList,
  IconRedo,
  IconStrikethrough,
  IconText,
  IconUnderline,
  IconUndo,
  IconUnorderedList,
} from '@sema4ai/icons';

import { $createHeadingNode, $createQuoteNode, $isHeadingNode, HeadingTagType } from '@lexical/rich-text';
import { $setBlocksType } from '@lexical/selection';
import { INSERT_ORDERED_LIST_COMMAND, INSERT_UNORDERED_LIST_COMMAND } from '@lexical/list';
import { $createCodeNode } from '@lexical/code';
import { INSERT_HORIZONTAL_RULE_COMMAND } from '@lexical/react/LexicalHorizontalRuleNode';
import { TOGGLE_LINK_COMMAND } from '@lexical/link';
import { INSERT_TABLE_COMMAND } from '@lexical/table';
import { SearchAndReplacePlugin } from './SearchAndReplacePlugin';
import { sanitizeUrl } from '../utils';

const LowPriority = 1;

export const Divider = () => {
  return <Box className="divider" />;
};

const blockTypeToBlockName = {
  bullet: 'Bulleted List',
  check: 'Check List',
  code: 'Code Block',
  h1: 'Heading 1',
  h2: 'Heading 2',
  h3: 'Heading 3',
  h4: 'Heading 4',
  h5: 'Heading 5',
  h6: 'Heading 6',
  number: 'Numbered List',
  paragraph: 'Normal',
  quote: 'Quote',
};

const HeadingItems = [
  {
    value: 'h1',
    label: 'Heading 1',
  },
  {
    value: 'h2',
    label: 'Heading 2',
  },
  {
    value: 'h3',
    label: 'Heading 3',
  },
  {
    value: 'h4',
    label: 'Heading 4',
  },
  {
    value: 'h5',
    label: 'Heading 5',
  },
];

export const ToolbarPlugin = () => {
  const [editor] = useLexicalComposerContext();
  const toolbarRef = useRef(null);

  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [isBold, setIsBold] = useState(false);
  const [isItalic, setIsItalic] = useState(false);
  const [isUnderline, setIsUnderline] = useState(false);
  const [isStrikethrough, setIsStrikethrough] = useState(false);
  const [isCode, setIsCode] = useState(false);

  const [blockType, setBlockType] = useState<keyof typeof blockTypeToBlockName>('paragraph');

  const $updateToolbar = useCallback(() => {
    const selection = $getSelection();
    if ($isRangeSelection(selection)) {
      // Update text format
      setIsBold(selection.hasFormat('bold'));
      setIsItalic(selection.hasFormat('italic'));
      setIsUnderline(selection.hasFormat('underline'));
      setIsStrikethrough(selection.hasFormat('strikethrough'));
      setIsCode(selection.hasFormat('code'));

      const anchorNode = selection.anchor.getNode();
      let element =
        anchorNode.getKey() === 'root'
          ? anchorNode
          : $findMatchingParent(anchorNode, (e) => {
              const parent = e.getParent();
              return parent !== null && $isRootOrShadowRoot(parent);
            });

      if (element === null) {
        element = anchorNode.getTopLevelElementOrThrow();
      }
      const type = $isHeadingNode(element) ? element.getTag() : element.getType();
      if (type in blockTypeToBlockName) {
        setBlockType(type as keyof typeof blockTypeToBlockName);
      }
    }
  }, []);

  const formatParagraph = () => {
    editor.update(() => {
      const selection = $getSelection();
      if ($isRangeSelection(selection)) {
        $setBlocksType(selection, () => $createParagraphNode());
      }
    });
  };

  const formatHeading = (headingSize: HeadingTagType, isAlreadySet?: boolean) => {
    if (isAlreadySet) {
      formatParagraph();
      return;
    }
    editor.update(() => {
      const selection = $getSelection();
      $setBlocksType(selection, () => $createHeadingNode(headingSize));
    });
  };

  useEffect(() => {
    return mergeRegister(
      editor.registerUpdateListener(({ editorState }) => {
        editorState.read(() => {
          $updateToolbar();
        });
      }),
      editor.registerCommand(
        SELECTION_CHANGE_COMMAND,
        () => {
          $updateToolbar();
          return false;
        },
        LowPriority,
      ),
      editor.registerCommand(
        CAN_UNDO_COMMAND,
        (payload) => {
          setCanUndo(payload);
          return false;
        },
        LowPriority,
      ),
      editor.registerCommand(
        CAN_REDO_COMMAND,
        (payload) => {
          setCanRedo(payload);
          return false;
        },
        LowPriority,
      ),
    );
  }, [editor, $updateToolbar]);

  return (
    <Box display="flex" flexDirection="row" items-center ref={toolbarRef}>
      <Tooltip text="Undo" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconUndo}
          disabled={!canUndo}
          onClick={() => {
            editor.dispatchCommand(UNDO_COMMAND, undefined);
          }}
          aria-label="Undo"
          round
        />
      </Tooltip>
      <Tooltip text="Redo" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconRedo}
          disabled={!canRedo}
          onClick={() => {
            editor.dispatchCommand(REDO_COMMAND, undefined);
          }}
          aria-label="Redo"
          round
        />
      </Tooltip>
      <Divider />
      <Select
        aria-label="Heading Select"
        items={HeadingItems}
        placeholder={blockType.charAt(0).toUpperCase() + blockType.slice(1)}
        value={blockType}
        iconLeft={IconHeading}
        onChange={(value) => formatHeading(value as HeadingTagType)}
        variant="ghost"
      />
      <Tooltip text="Text" className="!dark-tooltip-sm">
        <Button
          variant={blockType === 'paragraph' ? 'secondary' : 'ghost'}
          icon={IconText}
          onClick={formatParagraph}
          aria-label="Format Paragraph"
          className="[&_div_div_svg]:!h-5 [&_div_div_svg]:!w-5"
          round
        />
      </Tooltip>
      <Divider />
      <Tooltip text="Bold" className="!dark-tooltip-sm">
        <Button
          variant={isBold ? 'secondary' : 'ghost'}
          icon={IconBold}
          onClick={() => {
            editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'bold');
          }}
          aria-label="Format Bold"
          className="[&_div_div_svg]:!h-5 [&_div_div_svg]:!w-5"
          round
        />
      </Tooltip>
      <Tooltip text="Italic" className="!dark-tooltip-sm">
        <Button
          variant={isItalic ? 'secondary' : 'ghost'}
          icon={IconItalic}
          onClick={() => {
            editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'italic');
          }}
          aria-label="Format Italics"
          className="[&_div_div_svg]:!h-5 [&_div_div_svg]:!w-5"
          round
        />
      </Tooltip>
      <Tooltip text="Underline" className="!dark-tooltip-sm">
        <Button
          variant={isUnderline ? 'secondary' : 'ghost'}
          icon={IconUnderline}
          onClick={() => {
            editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'underline');
          }}
          aria-label="Format Underline"
          className="[&_div_div_svg]:!h-5 [&_div_div_svg]:!w-5"
          round
        />
      </Tooltip>
      <Tooltip text="Strikethrough" className="!dark-tooltip-sm">
        <Button
          variant={isStrikethrough ? 'secondary' : 'ghost'}
          icon={IconStrikethrough}
          onClick={() => {
            editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'strikethrough');
          }}
          aria-label="Format Strikethrough"
          className="[&_div_div_svg]:!h-5 [&_div_div_svg]:!w-5"
          round
        />
      </Tooltip>
      <Tooltip text="Code Line" className="!dark-tooltip-sm">
        <Button
          variant={isCode ? 'secondary' : 'ghost'}
          icon={IconCode3}
          onClick={() => {
            editor.dispatchCommand(FORMAT_TEXT_COMMAND, 'code');
          }}
          aria-label="Format Code"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Divider />
      <Tooltip text="Quote Block" className="!dark-tooltip-sm">
        <Button
          variant={blockType === 'quote' ? 'secondary' : 'ghost'}
          icon={IconBlockquote}
          onClick={() => {
            editor.update(() => {
              const selection = $getSelection();
              if ($isRangeSelection(selection)) {
                $setBlocksType(selection, () => $createQuoteNode());
              }
            });
          }}
          aria-label="BlockQuote"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Code Block" className="!dark-tooltip-sm">
        <Button
          variant={isCode ? 'secondary' : 'ghost'}
          icon={IconCode}
          onClick={() => {
            editor.update(() => {
              let selection = $getSelection();

              if (selection !== null) {
                if (selection.isCollapsed()) {
                  $setBlocksType(selection, () => $createCodeNode());
                } else {
                  const textContent = selection.getTextContent();
                  const codeNode = $createCodeNode();
                  selection.insertNodes([codeNode]);
                  selection = $getSelection();
                  if ($isRangeSelection(selection)) {
                    selection.insertRawText(textContent);
                  }
                }
              }
            });
          }}
          aria-label="CodeBlock"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Horizontal Rule" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconFileScan}
          onClick={() => {
            editor.dispatchCommand(INSERT_HORIZONTAL_RULE_COMMAND, undefined);
          }}
          aria-label="HorizontalRule"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Link" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconLink}
          onClick={() => {
            editor.dispatchCommand(TOGGLE_LINK_COMMAND, sanitizeUrl('https://'));
          }}
          aria-label="LinkCommand"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Divider />
      <Tooltip text="Bullet List" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconUnorderedList}
          onClick={() => {
            editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined);
          }}
          aria-label="Bullet List"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Number List" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconNumberedList}
          onClick={() => {
            editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined);
          }}
          aria-label="Number List"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Table" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconDbTable}
          onClick={() => {
            editor.dispatchCommand(INSERT_TABLE_COMMAND, { rows: '4', columns: '6', includeHeaders: true });
          }}
          aria-label="Table"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Divider />
      <Tooltip text="Indent" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconIndentLeft}
          onClick={() => {
            editor.dispatchCommand(INDENT_CONTENT_COMMAND, undefined);
          }}
          aria-label="Indent"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Tooltip text="Outdent" className="!dark-tooltip-sm">
        <Button
          variant="ghost"
          icon={IconIndentRight}
          onClick={() => {
            editor.dispatchCommand(OUTDENT_CONTENT_COMMAND, undefined);
          }}
          aria-label="Outdent"
          className="[&_div_div_svg]:!h-6 [&_div_div_svg]:!w-6"
          round
        />
      </Tooltip>
      <Divider />
      <SearchAndReplacePlugin />
    </Box>
  );
};
