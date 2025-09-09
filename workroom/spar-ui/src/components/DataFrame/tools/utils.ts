export const getIsSupportedDataFrameFile = <ThreadFile extends { mime_type?: string; file_ref?: string } | undefined>(
  threadFile?: ThreadFile,
): boolean => {
  switch (threadFile?.mime_type) {
    case 'text/csv':
    case 'application/csv':
    case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    case 'application/vnd.oasis.opendocument.spreadsheet':
      return true;
    default:
      return false;
  }
};
