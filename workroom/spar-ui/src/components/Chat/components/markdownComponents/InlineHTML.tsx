import { FC, useCallback, useMemo } from 'react';
import DOMPurify from 'dompurify';

interface Props {
  content: string;
}

const sanitizeContent = (content: string) => {
  return DOMPurify.sanitize(content, { WHOLE_DOCUMENT: true });
};

export const InlineHTML: FC<Props> = ({ content }) => {
  const sanitizedContent = useMemo(() => sanitizeContent(content), [content]);

  const handleRef = useCallback(
    (element: HTMLDivElement | null) => {
      if (!element) return;

      const shadowRoot = element.shadowRoot || element.attachShadow({ mode: 'open' });
      shadowRoot.innerHTML = sanitizedContent;
    },
    [sanitizedContent],
  );

  return <div ref={handleRef} />;
};
