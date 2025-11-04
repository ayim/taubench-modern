import { FC, useRef } from 'react';
import { styled } from '@sema4ai/theme';
import { useVirtualizer } from '@tanstack/react-virtual';

type Props<T extends object> = {
  items: T[];
  itemHeight: number;
  renderComponent: FC<{ item: T }>;
  pagination?: {
    hasMore: boolean;
    isFetchingMore: boolean;
    onLoadMore: () => void;
  };
  itemKey: keyof T;
};

const Container = styled.div`
  height: auto;
  overflow-y: auto;
  overflow-anchor: none;

  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari, Opera */
  }

  &:hover {
    scrollbar-width: var(--scrollbar-width);
    -ms-overflow-style: auto;

    &::-webkit-scrollbar {
      display: block;
    }
  }
`;

const ScrollContainer = styled.div`
  position: relative;

  > div {
    position: absolute;
    top: 0px;
    left: 0px;
    width: 100%;
  }
`;

export const VirtualList = <T extends object>({
  items,
  itemHeight,
  renderComponent: RenderComponent,
  pagination,
  itemKey,
}: Props<T>) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const count = items.length;

  const virtualizer = useVirtualizer({
    count,
    getScrollElement: () => containerRef.current,
    estimateSize: () => itemHeight,
    overscan: 3,
    onChange: (instance) => {
      if (!pagination) {
        return;
      }

      const { hasMore, isFetchingMore, onLoadMore } = pagination;

      if (!hasMore || isFetchingMore) {
        return;
      }

      const virtualItemsFromInstance = instance.getVirtualItems();
      const lastItem = virtualItemsFromInstance.at(-1);

      if (lastItem && lastItem.index >= items.length - 1) {
        onLoadMore();
      }
    },
  });

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <Container ref={containerRef}>
      <ScrollContainer
        style={{
          height: virtualizer.getTotalSize(),
        }}
        ref={scrollContainerRef}
      >
        <div
          style={{
            transform: `translateY(${virtualItems[0]?.start ?? 0}px)`,
          }}
        >
          {virtualItems.map((virtualRow) => {
            const item = items[virtualRow.index];
            return <RenderComponent data-index={virtualRow.index} key={String(item[itemKey])} item={item} />;
          })}
        </div>
      </ScrollContainer>
    </Container>
  );
};
