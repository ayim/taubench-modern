import { FC, ReactNode, useEffect, useRef } from 'react';
import { styled } from '@sema4ai/theme';

type Props = {
  children?: ReactNode;
};

const Container = styled.div`
  position: sticky;
  bottom: -1px;
  display: flex;
  gap: ${({ theme }) => theme.space.$8};
  justify-content: flex-start;
  flex-direction: row-reverse;
  background: ${({ theme }) => theme.colors.background.primary.color};
  padding: ${({ theme }) => theme.space.$24} 0;
  margin-top: ${({ theme }) => theme.space.$40};

  &.pinned {
    border-top: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  }
`;

export const ActionSticky: FC<Props> = ({ children }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([e]) => e.target.classList.toggle('pinned', e.intersectionRatio < 1), {
      threshold: [1],
    });

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      if (containerRef.current) {
        observer.unobserve(containerRef.current);
      }
    };
  }, []);

  return <Container ref={containerRef}>{children}</Container>;
};
