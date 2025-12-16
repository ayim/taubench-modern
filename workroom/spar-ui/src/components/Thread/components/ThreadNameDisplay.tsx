import { FC, useEffect, useRef, useState } from 'react';
import { styled } from '@sema4ai/theme';

type ThreadNameDisplayProps = {
  name?: string | null;
  threadId?: string | null;
};

const renameRevealKeyframes = `
  @keyframes threadNameReveal {
    0% {
      opacity: 0.5;
      transform: translateY(-2px);
    }

    100% {
      opacity: 1;
      transform: translateY(0);
    }
  }
`;

const caretBlinkKeyframes = `
  @keyframes threadCaretBlink {
    0%,
    55% {
      opacity: 1;
    }

    56%,
    100% {
      opacity: 0;
    }
  }
`;

const AnimatedThreadNameLabel = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.space.$4};
  max-width: 100%;
`;

const AnimatedThreadNameText = styled('span')<{ $animate: boolean }>`
  ${renameRevealKeyframes}
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;

  ${({ $animate }) =>
    $animate
      ? `
    animation: threadNameReveal 420ms ease;
  `
      : 'animation: none;'};
`;

const AnimatedCaret = styled('span')<{ $visible: boolean }>`
  ${caretBlinkKeyframes}
  display: inline-block;
  width: 2px;
  height: 1.1em;
  background-color: ${({ theme }) => theme.colors.content.primary.color};
  opacity: ${({ $visible }) => ($visible ? 1 : 0)};
  transform-origin: center;
  flex-shrink: 0;
  ${({ $visible }) =>
    $visible
      ? `
    animation: threadCaretBlink 680ms steps(1, end) infinite;
  `
      : 'animation: none;'};
`;

const isSameName = (left: string, right: string) => {
  return left.trim() === right.trim();
};

export const ThreadNameDisplay: FC<ThreadNameDisplayProps> = ({ name, threadId }) => {
  const initialName = name ?? '';
  const previousNameRef = useRef<string>(initialName);
  const timeoutRef = useRef<number | undefined>(undefined);
  const cleanedUpThreadId = threadId ?? '';
  const threadIdRef = useRef(cleanedUpThreadId);
  const hasThreadChanged = threadIdRef.current !== '' && threadIdRef.current !== cleanedUpThreadId;
  const [currentName, setCurrentName] = useState(
    hasThreadChanged || isSameName(previousNameRef.current, initialName) ? initialName : initialName.substring(0, 1),
  );
  const recursion = (typing: string, length: number) => {
    if (timeoutRef.current !== undefined) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = undefined;
    }
    if (length <= typing.length) {
      const typingProgress = typing.substring(0, length);
      previousNameRef.current = typingProgress;

      setCurrentName(typingProgress);
      timeoutRef.current = window.setTimeout(() => recursion(typing, length + 1), 38);
      return undefined;
    }

    previousNameRef.current = typing;
    return undefined;
  };

  /**
   * Show animation if thread hasn't changed and name is different from previous name
   */
  const showRenameAnimation = !hasThreadChanged && !isSameName(previousNameRef.current, initialName);
  /**
   * - if initialName + showRenameAnimation, start the animation
   * - if animation started and showRenameAnimation turns to false run useEffect cleanup to stop the animation
   */
  useEffect(() => {
    if (showRenameAnimation) {
      recursion(initialName, 1);
      return () => {
        if (timeoutRef.current !== undefined) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = undefined;
          setCurrentName(initialName);
        }
      };
    }
    threadIdRef.current = cleanedUpThreadId;
    previousNameRef.current = initialName;
    return undefined;
  }, [initialName, showRenameAnimation]);

  return (
    <AnimatedThreadNameLabel>
      <AnimatedThreadNameText $animate={showRenameAnimation}>{currentName}</AnimatedThreadNameText>
      <AnimatedCaret $visible={showRenameAnimation} />
    </AnimatedThreadNameLabel>
  );
};
