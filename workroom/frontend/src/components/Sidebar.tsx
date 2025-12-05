import { FC, ReactNode, useEffect, useRef } from 'react';
import { styled } from '@sema4ai/theme';
import { ResizeHandle, useLocalStorage, useResizeHandle } from '@sema4ai/components';

type Props = {
  name: string;
  children: ReactNode;
};

const Container = styled.div`
  position: relative;
  padding: ${({ theme }) => theme.space.$8};
  overflow-x: hidden;
  width: var(--width);
  height: calc(100vh - ${({ theme }) => theme.sizes.$64});
  display: flex;
  flex-direction: column;

  ${({ theme }) => theme.screen.m} {
    height: calc(100vh - 52px);
  }
`;

export const Sidebar: FC<Props> = ({ children, name }) => {
  const { storageValue: initialWidth, setStorageValue: setInitialWidth } = useLocalStorage<number>({
    key: `sidebar-${name}-width`,
    defaultValue: 248,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const { width: resizeWidth, resizeHandlerRef } = useResizeHandle({
    initialWidth,
    minWidth: 325,
    maxWidth: Infinity,
    dependencies: [],
    position: 'left',
  });

  useEffect(() => {
    containerRef.current?.style.setProperty('--width', `${resizeWidth}px`);
    setInitialWidth(resizeWidth);
  }, [resizeWidth, setInitialWidth]);

  return (
    <Container ref={containerRef} id="thread-details-sidebar">
      {children}
      <ResizeHandle ref={resizeHandlerRef} position="left" />
    </Container>
  );
};
