import { Box } from '@sema4ai/components';
import { IconChevronRight } from '@sema4ai/icons';
import { styled, Color } from '@sema4ai/theme';
import { memo, useCallback, useEffect, useState, ReactNode } from 'react';

interface CollapsibleProps {
  header: ReactNode;
  headerRight?: ReactNode;
  children: ReactNode;
  isExpandable?: boolean;
  onExpand?: () => void;
  dataTestId?: string;
  backgroundColor?: Color;
  isComplete?: boolean;
}

/**
 * Duration of expand-collapse animation
 */
const animationDuration = 300;


const Container = styled(Box)`
  overflow: hidden;
`;

const ContentContainer = styled(Box)`
  max-height: 0;
  overflow: hidden;
  transition: max-height ${animationDuration}ms ease-in-out;

  &.expanded {
    max-height: 1000px; /* Large enough to accommodate content */
  }
`;

const Collapsible = memo(
  ({
    header,
    headerRight,
    children,
    isExpandable = true,
    onExpand,
    dataTestId,
    backgroundColor = 'transparent',
    isComplete,
  }: CollapsibleProps) => {
    // State to handle the expansion
    const [isExpanded, setIsExpanded] = useState(() => {
      if (isComplete !== undefined) {
        return !isComplete;
      }
      return false;
    });

    const toggleExpanded = useCallback(() => {
      if (!isExpandable) return;
      setIsExpanded((v) => {
        const newValue = !v;
        if (!v && onExpand) {
          onExpand();
        }
        return newValue;
      });
    }, [isExpandable, onExpand]);

    // Update expansion state when isComplete changes
    useEffect(() => {
      if (isComplete !== undefined) {
        setIsExpanded(!isComplete);
      }
    }, [isComplete]);

    return (
      <Container backgroundColor={backgroundColor} data-testid={dataTestId}>
        <Box
          display="flex"
          alignItems="center"
          as="span"
          onClick={toggleExpanded}
          style={{ cursor: isExpandable ? 'pointer' : 'default' }}
        >
          {header}
          {isExpandable && (
            <Box
              style={{
                transition: 'transform 300ms ease-in-out',
                transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)'
              }}
            >
              <IconChevronRight />
            </Box>
          )}
          {headerRight && !isExpanded && (
            <Box marginLeft="auto" marginRight={12} style={{ flexShrink: 0 }}>
              {headerRight}
            </Box>
          )}
        </Box>
        <ContentContainer className={isExpanded ? 'expanded' : ''}>
          {isExpanded && <Box padding={4}>{children}</Box>}
        </ContentContainer>
      </Container>
    );
  },
);

export default Collapsible;
