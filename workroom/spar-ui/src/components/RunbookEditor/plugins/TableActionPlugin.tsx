/* eslint-disable camelcase */
/* eslint-disable no-underscore-dangle */
import { JSX, useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { $getSelection, $isRangeSelection, SELECTION_CHANGE_COMMAND, COMMAND_PRIORITY_LOW } from 'lexical';
import {
  $isTableCellNode,
  $isTableNode,
  TableCellNode,
  $insertTableColumn__EXPERIMENTAL,
  $insertTableRow__EXPERIMENTAL,
  $deleteTableColumn__EXPERIMENTAL,
  $deleteTableRow__EXPERIMENTAL,
} from '@lexical/table';
import { $findMatchingParent } from '@lexical/utils';
import { Box, Button, Divider, Menu, useSnackbar } from '@sema4ai/components';
import {
  IconAlignArrowDown,
  IconAlignArrowLeft,
  IconAlignArrowRight,
  IconAlignArrowUp,
  IconMenu2,
  IconTrash,
  IconTrash2,
} from '@sema4ai/icons';

interface TableActionPosition {
  top: number;
  right: number;
  show: boolean;
}

interface TableActionHandlers {
  onInsertColumnLeft: () => void;
  onInsertColumnRight: () => void;
  onInsertRowAbove: () => void;
  onInsertRowBelow: () => void;
  onDeleteColumn: () => void;
  onDeleteRow: () => void;
  onDeleteTable: () => void;
}

const TableActionButton = ({
  position,
  handlers,
}: {
  position: TableActionPosition;
  handlers: TableActionHandlers;
}): JSX.Element => {
  const buttonRef = useRef<HTMLDivElement>(null);

  if (!position.show) {
    return <div ref={buttonRef} className="table-action-button" style={{ opacity: 0, pointerEvents: 'none' }} />;
  }

  return (
    <Box
      ref={buttonRef}
      className="table-action-button"
      style={{
        position: 'absolute',
        top: `${position.top}px`,
        right: `${position.right}px`,
        zIndex: 10,
        opacity: 1,
        transition: 'opacity 0.2s ease-in-out',
      }}
    >
      <Menu trigger={<Button variant="link" icon={IconMenu2} aria-label="Table Actions" size="small" round />}>
        <Menu.Item icon={IconAlignArrowLeft} onClick={handlers.onInsertColumnLeft}>
          Insert column left
        </Menu.Item>
        <Menu.Item icon={IconAlignArrowRight} onClick={handlers.onInsertColumnRight}>
          Insert column right
        </Menu.Item>
        <Menu.Item icon={IconAlignArrowUp} onClick={handlers.onInsertRowAbove}>
          Insert row above
        </Menu.Item>
        <Menu.Item icon={IconAlignArrowDown} onClick={handlers.onInsertRowBelow}>
          Insert row below
        </Menu.Item>
        <Divider />
        <Menu.Item icon={IconTrash} onClick={handlers.onDeleteColumn}>
          Delete column
        </Menu.Item>
        <Menu.Item icon={IconTrash} onClick={handlers.onDeleteRow}>
          Delete row
        </Menu.Item>
        <Divider />
        <Menu.Item icon={IconTrash2} onClick={handlers.onDeleteTable}>
          Delete table
        </Menu.Item>
      </Menu>
    </Box>
  );
};

export default function TableActionPlugin({
  anchorElem = document.body,
}: {
  anchorElem?: HTMLElement;
}): JSX.Element | null {
  const { addSnackbar } = useSnackbar();

  const [editor] = useLexicalComposerContext();
  const [position, setPosition] = useState<TableActionPosition>({
    top: 0,
    right: 0,
    show: false,
  });
  const [currentTableCell, setCurrentTableCell] = useState<TableCellNode | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isScrollingRef = useRef<boolean>(false);

  const updateButtonPosition = useCallback(
    (forceHide = false) => {
      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }

      timeoutRef.current = setTimeout(() => {
        editor.getEditorState().read(() => {
          const selection = $getSelection();

          if (!$isRangeSelection(selection)) {
            setPosition((prev) => ({ ...prev, show: false }));
            setCurrentTableCell(null);
            return;
          }

          const anchorNode = selection.anchor.getNode();

          // Find if we're inside a table cell
          const tableCellNode = $findMatchingParent(anchorNode, $isTableCellNode);

          if (!tableCellNode) {
            setPosition((prev) => ({ ...prev, show: false }));
            setCurrentTableCell(null);
            return;
          }

          // Find the table node
          const tableNode = $findMatchingParent(tableCellNode, $isTableNode);

          if (!tableNode) {
            setPosition((prev) => ({ ...prev, show: false }));
            setCurrentTableCell(null);
            return;
          }

          setCurrentTableCell(tableCellNode);

          // Get the DOM element for the active cell
          const cellElement = editor.getElementByKey(tableCellNode.getKey());
          const editorContainer = editor.getRootElement();

          if (cellElement && editorContainer) {
            const cellRect = cellElement.getBoundingClientRect();
            const containerRect = editorContainer.getBoundingClientRect();

            // Position the button on the top right corner of the active cell
            // Use viewport coordinates directly since the button is absolutely positioned
            const topPosition = cellRect.top - containerRect.top + 4;
            const rightPosition = containerRect.right - cellRect.right + 4;

            setPosition({
              top: topPosition,
              right: rightPosition,
              show: !forceHide && !isScrollingRef.current,
            });
          }
        });
      }, 100);
    },
    [editor],
  );

  const handleInsertColumnLeft = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $insertTableColumn__EXPERIMENTAL(false);
      } catch (error) {
        addSnackbar({
          message: `Failed to insert column left: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleInsertColumnRight = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $insertTableColumn__EXPERIMENTAL(true);
      } catch (error) {
        addSnackbar({
          message: `Failed to insert column right: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleInsertRowAbove = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $insertTableRow__EXPERIMENTAL(false);
      } catch (error) {
        addSnackbar({
          message: `Failed to insert row above: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleInsertRowBelow = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $insertTableRow__EXPERIMENTAL(true);
      } catch (error) {
        addSnackbar({
          message: `Failed to insert row below: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleDeleteColumn = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $deleteTableColumn__EXPERIMENTAL();
      } catch (error) {
        addSnackbar({
          message: `Failed to delete column: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleDeleteRow = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        $deleteTableRow__EXPERIMENTAL();
      } catch (error) {
        addSnackbar({
          message: `Failed to delete row: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  const handleDeleteTable = useCallback(() => {
    if (!currentTableCell) return;
    editor.update(() => {
      try {
        const selection = $getSelection();
        if (!$isRangeSelection(selection)) return;

        const anchorNode = selection.anchor.getNode();
        const tableCellNode = $findMatchingParent(anchorNode, $isTableCellNode);
        if (!tableCellNode) return;

        const tableNode = $findMatchingParent(tableCellNode, $isTableNode);
        if (tableNode) {
          tableNode.remove();
        }
      } catch (error) {
        addSnackbar({
          message: `Failed to delete table: ${error}`,
          variant: 'danger',
        });
      }
    });
  }, [editor, currentTableCell]);

  useEffect(() => {
    return editor.registerCommand(
      SELECTION_CHANGE_COMMAND,
      () => {
        updateButtonPosition();
        return false;
      },
      COMMAND_PRIORITY_LOW,
    );
  }, [editor, updateButtonPosition]);

  useEffect(() => {
    const editorContainer = editor.getRootElement();
    if (!editorContainer) return undefined;

    const handleScroll = () => {
      // Hide button immediately when scrolling starts
      isScrollingRef.current = true;
      setPosition((prev) => ({ ...prev, show: false }));

      // Clear any existing scroll timeout
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }

      // Show button again after scrolling stops (150ms of inactivity)
      scrollTimeoutRef.current = setTimeout(() => {
        isScrollingRef.current = false;
        updateButtonPosition();
      }, 150);
    };

    // Listen for scroll events on the editor container
    editorContainer.addEventListener('scroll', handleScroll, { passive: true });
    window.addEventListener('resize', handleScroll);

    // Also listen for scroll events on parent containers that might be scrollable
    const parentScrollable = editorContainer.parentElement;
    if (parentScrollable) {
      parentScrollable.addEventListener('scroll', handleScroll, { passive: true });
    }

    return () => {
      editorContainer.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleScroll);
      if (parentScrollable) {
        parentScrollable.removeEventListener('scroll', handleScroll);
      }
    };
  }, [editor, updateButtonPosition]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, []);

  const handlers: TableActionHandlers = {
    onInsertColumnLeft: handleInsertColumnLeft,
    onInsertColumnRight: handleInsertColumnRight,
    onInsertRowAbove: handleInsertRowAbove,
    onInsertRowBelow: handleInsertRowBelow,
    onDeleteColumn: handleDeleteColumn,
    onDeleteRow: handleDeleteRow,
    onDeleteTable: handleDeleteTable,
  };

  return createPortal(<TableActionButton position={position} handlers={handlers} />, anchorElem);
}
