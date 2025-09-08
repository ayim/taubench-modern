import { IconTableRows, IconType } from '@sema4ai/icons';
import { IconPDF, IconAnyFile, IconWord, IconExcel } from '@sema4ai/icons/logos';

export function getFileTypeIcon(fileType: string): IconType {
  switch (fileType) {
    case 'application/pdf':
    case 'pdf':
    case 'PDF':
      return IconPDF;
    case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
    case 'application/msword':
    case 'doc':
    case 'docx':
      return IconWord;
    case 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
    case 'application/vnd.ms-excel':
    case 'xls':
    case 'xlsx':
      return IconExcel;
    case 'csv':
      return IconTableRows;
    default:
      return IconAnyFile;
  }
}

export const snakeCaseToTitleCase = (str: string) => {
  return str.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
};

export const getFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(sizes.length - 1, Math.floor(Math.log(bytes) / Math.log(k)));

  return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
};
