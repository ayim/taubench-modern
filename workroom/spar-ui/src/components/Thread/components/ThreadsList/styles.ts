import { Box } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

export const ResizeHandle = styled.button`
  height: 1px;
  cursor: ns-resize;
  background: ${({ theme }) => theme.colors.border.subtle.color};
  border: none;
  padding: 0;
  position: relative;
  width: 100%;
  transition: ${({ theme }) => theme.transition.normal};

  &:hover {
    height: 2px;
    background: ${({ theme }) => theme.colors.border.subtle.hovered.color};
  }

  &:hover::before {
    content: '';
    position: absolute;
    top: -2px;
    left: 0;
    right: 0;
    height: 8px;
    background: transparent;
  }
`;

export const Header = styled(Box)`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.space.$8};
  gap: ${({ theme }) => theme.space.$8};

  button {
    padding: 0;
    min-width: auto;
  }
`;

export const SectionHeader = styled(Box)`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.space.$8};
  gap: ${({ theme }) => theme.space.$8};
  cursor: pointer;

  button {
    padding: 0;
    min-width: auto;
  }
`;

export const ScrollableContainer = styled(Box)`
  display: flex;
  min-height: 0;
  overflow: auto;
  flex-direction: column;
  padding-left: ${({ theme }) => theme.space.$12};
  margin-left: -${({ theme }) => theme.space.$12};
  height: auto;

  scrollbar-width: none;
  -ms-overflow-style: none;

  &::-webkit-scrollbar {
    display: none;
  }

  &:hover {
    scrollbar-width: auto;
    -ms-overflow-style: auto;

    &::-webkit-scrollbar {
      display: block;
    }
  }
`;

export const AnimatedSection = styled(Box)<{ isExpanded: boolean }>`
  overflow: hidden;
  transition:
    max-height 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.2s ease-in-out;
  max-height: ${({ isExpanded }) => (isExpanded ? '1000px' : '0px')};
  opacity: ${({ isExpanded }) => (isExpanded ? 1 : 0)};
  display: flex;
  flex-direction: column;
  flex: ${({ isExpanded }) => (isExpanded ? 1 : 0)};
  min-height: 0;
`;

export const AnimatedEvalSection = styled(Box)<{
  isExpanded: boolean;
  height: string;
  enableTransition?: boolean;
}>`
  overflow: hidden;
  transition: ${({ enableTransition = true }) =>
    enableTransition ? 'height 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.2s ease-in-out' : 'none'};
  height: ${({ isExpanded, height }) => (isExpanded ? height : '0px')};
  opacity: ${({ isExpanded }) => (isExpanded ? 1 : 0)};
  display: flex;
  flex-direction: column;
  min-height: 0;
  transform-origin: top;
`;
