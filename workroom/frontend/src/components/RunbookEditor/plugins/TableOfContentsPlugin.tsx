import type { TableOfContentsEntry } from '@lexical/react/LexicalTableOfContentsPlugin';
import type { HeadingTagType } from '@lexical/rich-text';
import type { NodeKey } from 'lexical';
import { styled } from '@sema4ai/theme';

import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { TableOfContentsPlugin as LexicalTableOfContentsPlugin } from '@lexical/react/LexicalTableOfContentsPlugin';
import { useEffect, useRef, useState } from 'react';
import { Box, Button, Typography } from '@sema4ai/components';
import { IconLayoutLeft } from '@sema4ai/icons';
import { Container } from './Container';

const MARGIN_ABOVE_EDITOR = 624;
const HEADING_WIDTH = 9;

function indent(tagName: HeadingTagType) {
  if (tagName === 'h2') {
    return 'heading2';
  }
  if (tagName === 'h3') {
    return 'heading3';
  }
  return 'heading1';
}

function isHeadingAtTheTopOfThePage(element: HTMLElement): boolean {
  const elementYPosition = element?.getClientRects()[0].y;
  return elementYPosition >= MARGIN_ABOVE_EDITOR && elementYPosition <= MARGIN_ABOVE_EDITOR + HEADING_WIDTH;
}
function isHeadingAboveViewport(element: HTMLElement): boolean {
  const elementYPosition = element?.getClientRects()[0].y;
  return elementYPosition < MARGIN_ABOVE_EDITOR;
}
function isHeadingBelowTheTopOfThePage(element: HTMLElement): boolean {
  const elementYPosition = element?.getClientRects()[0].y;
  return elementYPosition >= MARGIN_ABOVE_EDITOR + HEADING_WIDTH;
}

const TableOfContentsList = ({ tableOfContents }: { tableOfContents: Array<TableOfContentsEntry> }) => {
  const [selectedKey, setSelectedKey] = useState('');
  const selectedIndex = useRef(0);
  const [editor] = useLexicalComposerContext();

  function scrollToNode(key: NodeKey, currIndex: number) {
    editor.getEditorState().read(() => {
      const domElement = editor.getElementByKey(key);
      if (domElement !== null) {
        domElement.scrollIntoView();
        setSelectedKey(key);
        selectedIndex.current = currIndex;
      }
    });
  }

  useEffect(() => {
    function scrollCallback() {
      if (tableOfContents.length !== 0 && selectedIndex.current < tableOfContents.length - 1) {
        let currentHeading = editor.getElementByKey(tableOfContents[selectedIndex.current][0]);
        if (currentHeading !== null) {
          if (isHeadingBelowTheTopOfThePage(currentHeading)) {
            // On natural scroll, user is scrolling up
            while (
              currentHeading !== null &&
              isHeadingBelowTheTopOfThePage(currentHeading) &&
              selectedIndex.current > 0
            ) {
              const prevHeading = editor.getElementByKey(tableOfContents[selectedIndex.current - 1][0]);
              if (
                prevHeading !== null &&
                (isHeadingAboveViewport(prevHeading) || isHeadingBelowTheTopOfThePage(prevHeading))
              ) {
                selectedIndex.current -= 1;
              }
              currentHeading = prevHeading;
            }
            const prevHeadingKey = tableOfContents[selectedIndex.current][0];
            setSelectedKey(prevHeadingKey);
          } else if (isHeadingAboveViewport(currentHeading)) {
            // On natural scroll, user is scrolling down
            while (
              currentHeading !== null &&
              isHeadingAboveViewport(currentHeading) &&
              selectedIndex.current < tableOfContents.length - 1
            ) {
              const nextHeading = editor.getElementByKey(tableOfContents[selectedIndex.current + 1][0]);
              if (
                nextHeading !== null &&
                (isHeadingAtTheTopOfThePage(nextHeading) || isHeadingAboveViewport(nextHeading))
              ) {
                selectedIndex.current += 1;
              }
              currentHeading = nextHeading;
            }
            const nextHeadingKey = tableOfContents[selectedIndex.current][0];
            setSelectedKey(nextHeadingKey);
          }
        }
      } else {
        selectedIndex.current = 0;
      }
    }
    let timerId: ReturnType<typeof setTimeout>;

    function debounceFunction(func: () => void, delay: number) {
      clearTimeout(timerId);
      timerId = setTimeout(func, delay);
    }

    function onScroll(): void {
      debounceFunction(scrollCallback, 10);
    }

    document.addEventListener('scroll', onScroll);
    return () => document.removeEventListener('scroll', onScroll);
  }, [tableOfContents, editor]);

  return (
    <Container className="table-of-contents">
      <ul className="headings">
        {tableOfContents.map(([key, text, tag], index) => {
          return (
            <Box
              className={`normal-heading-wrapper ${selectedKey === key ? 'selected-heading-wrapper' : ''}`}
              key={key}
            >
              <Box onClick={() => scrollToNode(key, index)} role="button" className={indent(tag)} tabIndex={0}>
                <li className={`normal-heading ${selectedKey === key ? 'selected-heading' : ''}`}>{text}</li>
              </Box>
            </Box>
          );
        })}
      </ul>
    </Container>
  );
};

const SidebarContainer = styled(Box)<{ $open: boolean }>`
  display: flex;
  flex-direction: column;
  height: 100%;
  width: ${({ $open }) => ($open ? '20%' : 'auto')};
  padding: ${({ theme }) => theme.space.$8} 0;
  gap: ${({ theme }) => theme.space.$16};
  background-color: ${({ theme }) => theme.colors.background.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-right: none;
  border-radius: ${({ theme }) => theme.radii.$8} 0 0 ${({ theme }) => theme.radii.$8};
`;

export const TableOfContentsPlugin = () => {
  const [showOutline, setShowOutline] = useState(false);

  if (!showOutline) {
    return (
      <SidebarContainer $open={false}>
        <Button
          variant="ghost-subtle"
          icon={IconLayoutLeft}
          round
          aria-label="Toggle Outline"
          onClick={() => setShowOutline(!showOutline)}
        />
      </SidebarContainer>
    );
  }

  return (
    <SidebarContainer $open>
      <Box display="flex" alignItems="center" justifyContent="space-between" pl="$16">
        <Typography variant="body-large" color="content.subtle" fontWeight="medium">
          Outline
        </Typography>
        <Button
          variant="ghost-subtle"
          icon={IconLayoutLeft}
          round
          aria-label="Toggle Outline"
          onClick={() => setShowOutline(!showOutline)}
        />
      </Box>
      <Box px="$10">
        <LexicalTableOfContentsPlugin>
          {(tableOfContents) => {
            return <TableOfContentsList tableOfContents={tableOfContents} />;
          }}
        </LexicalTableOfContentsPlugin>
      </Box>
    </SidebarContainer>
  );
};
