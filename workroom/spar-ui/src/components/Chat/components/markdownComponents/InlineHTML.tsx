import { FC, useMemo } from 'react';
import DOMPurify from 'dompurify';

interface Props {
  content: string;
}

const sanitizeContent = (content: string) => {
  return DOMPurify.sanitize(content);
};

export const InlineHTML: FC<Props> = ({ content }) => {
  const sanitizedContent = useMemo(() => sanitizeContent(content), [content]);

  // eslint-disable-next-line react/no-danger
  return <div dangerouslySetInnerHTML={{ __html: sanitizedContent }} />;
};
