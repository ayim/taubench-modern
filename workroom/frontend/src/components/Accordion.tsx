import { FC, ReactNode, useCallback, useRef, useState } from 'react';
import { Box, Transition, Typography } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconChevronDown } from '@sema4ai/icons';

type Props = {
  title: string;
  description?: string;
  children: ReactNode;
};

const Toggle = styled.button`
  display: flex;
  text-align: left;
  background: none;
`;

export const Accordion: FC<Props> = ({ title, description, children }) => {
  const contentRef = useRef<HTMLDivElement>(null);
  const [isOpen, setIsOpen] = useState(false);

  const toggle = useCallback(() => {
    setIsOpen(!isOpen);
  }, [isOpen]);

  return (
    <>
      <Toggle type="button" onClick={toggle}>
        <Typography variant="display-small" fontWeight="medium">
          {title}
        </Typography>
        <IconChevronDown />
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
