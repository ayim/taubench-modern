import { FC, ReactNode, useEffect, useRef } from 'react';
import { styled } from '@sema4ai/theme';
import { ResizeHandle, useLocalStorage, useResizeHandle } from '@sema4ai/components';

type Props = {
  name: string;
  children: ReactNode;
};

const Container = styled.div`
  position: relative;
  user-select: none;
  padding: ${({ theme }) => theme.space.$8};
  overflow: hidden;
  width: var(--width);
`;

// TODO: The behaviour and layout of the sidebar will change once final design is there
export const Sidebar: FC<Props> = ({ children, name }) => {
  const { storageValue: initialWidth, setStorageValue: setInitialWidth } = useLocalStorage<number>({
    key: `sidebar-${name}-width`,
    defaultValue: 240,
  });

  const containerRef = useRef<HTMLDivElement>(null);
  const { width: resizeWidth, resizeHandlerRef } = useResizeHandle({
    initialWidth,
    minWidth: 200,
    maxWidth: 400,
    dependencies: [],
    position: 'left',
  });

  useEffect(() => {
    containerRef.current?.style.setProperty('--width', `${resizeWidth}px`);
    setInitialWidth(resizeWidth);
  }, [resizeWidth, setInitialWidth]);

  return (
    <Container ref={containerRef}>
      {children}
      <ResizeHandle ref={resizeHandlerRef} position="left" />
    </Container>
  );
};
