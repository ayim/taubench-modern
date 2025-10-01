export const getContentType = ({ fileName }: { fileName: string }): string => {
  if (fileName.toLowerCase().endsWith('.html')) {
    return 'text/html';
  }

  return 'text/plain';
};
