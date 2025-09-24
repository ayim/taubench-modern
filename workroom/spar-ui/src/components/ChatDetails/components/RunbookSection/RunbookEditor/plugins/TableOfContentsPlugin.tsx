import type { TableOfContentsEntry } from '@lexical/react/LexicalTableOfContentsPlugin';
import type { NodeKey } from 'lexical';

import { useLexicalComposerContext } from '@lexical/react/LexicalComposerContext';
import { TableOfContentsPlugin as LexicalTableOfContentsPlugin } from '@lexical/react/LexicalTableOfContentsPlugin';
import { JSX, useEffect, useRef, useState } from 'react';
import {
  StyledHeadings,
  StyledNormalHeading,
  StyledNormalHeadingWrapper,
  StyledTableOfContents,
  StyledHeadingItem,
} from './styledComponents';

const MARGIN_ABOVE_EDITOR = 624;
const HEADING_WIDTH = 9;

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

const TableOfContentsList = ({ tableOfContents }: { tableOfContents: Array<TableOfContentsEntry> }): JSX.Element => {
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
    <StyledTableOfContents>
      <StyledHeadings>
        {tableOfContents.map(([key, text, tag], index) => {
          return (
            <StyledNormalHeadingWrapper key={key} selected={selectedKey === key}>
              <StyledHeadingItem onClick={() => scrollToNode(key, index)} role="button" headingLevel={tag} tabIndex={0}>
                <StyledNormalHeading selected={selectedKey === key}>{text}</StyledNormalHeading>
              </StyledHeadingItem>
            </StyledNormalHeadingWrapper>
          );
        })}
      </StyledHeadings>
    </StyledTableOfContents>
  );
};

const TableOfContentsPlugin = () => {
  return (
    <LexicalTableOfContentsPlugin>
      {(tableOfContents) => {
        return <TableOfContentsList tableOfContents={tableOfContents} />;
      }}
    </LexicalTableOfContentsPlugin>
  );
};

export default TableOfContentsPlugin;
