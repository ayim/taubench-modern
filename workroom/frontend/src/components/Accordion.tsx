import { FC, ReactNode, useCallback, useRef, useState } from 'react';
import { Box, Transition, Typography } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconChevronDown, IconChevronUp } from '@sema4ai/icons';

type Props = {
  title: string;
  size?: 'small' | 'medium';
  description?: string;
  children: ReactNode;
  open?: boolean;
};

const Toggle = styled.button`
  display: flex;
  align-items: center;
  text-align: left;
  background: none;
`;

export const Accordion: FC<Props> = ({ title, description, children, size, open: initialOpen }) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(initialOpen ?? false);

  const toggle = useCallback(() => {
    setIsOpen(!isOpen);
  }, [isOpen]);

  const titleVariant = size === 'small' ? 'body-medium' : 'display-small';

  return (
    <>
      <Toggle type="button" onClick={toggle}>
        <Typography variant={titleVariant} fontWeight="medium">
          {title}
        </Typography>
        {isOpen ? <IconChevronUp /> : <IconChevronDown />}
      </Toggle>
      {description && (
        <Typography variant="body-medium" color="content.subtle">
          {description}
        </Typography>
      )}
      <Box ref={contentRef}>
        <Transition.Collapse in={isOpen} nodeRef={contentRef}>
          <Box py="$24">{children}</Box>
        </Transition.Collapse>
      </Box>
    </>
  );
};
