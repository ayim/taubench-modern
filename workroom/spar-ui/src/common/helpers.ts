import { IconTableRows, IconType } from '@sema4ai/icons';
import { IconAnyFile, IconExcel, IconPDF, IconWord } from '@sema4ai/icons/logos';
import { Accept } from 'react-dropzone';

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

export const snakeToCapitalCase = (str: string) => {
  return str.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
};

export const getFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.min(sizes.length - 1, Math.floor(Math.log(bytes) / Math.log(k)));

  return `${parseFloat((bytes / k ** i).toFixed(2))} ${sizes[i]}`;
};

/**
 * Gets the list of supported extension from accept property of dropzon config
 */
export const getSupportedExtensions = (accept: Accept): string[] => {
  return Array.from(new Set(Object.values(accept).flat())).sort();
};

export const formatWorkItemStatus = (status: string): string => {
  return status
    .toLowerCase()
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

export const formatDateTime = (dateString: string | undefined): string => {
  if (!dateString) {
    return '';
  }

  const date = new Date(dateString);

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const datePart = new Intl.DateTimeFormat('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }).format(date);

  const timePart = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);

  return `${datePart} at ${timePart}`;
};

export const formatShortDateTime = (dateString: string | undefined): string => {
  if (!dateString) {
    return '';
  }

  const date = new Date(dateString);

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const monthShort = new Intl.DateTimeFormat('en-US', {
    month: 'short',
  }).format(date);

  const day = new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
  }).format(date);

  const time = new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  }).format(date);

  return `${monthShort} ${day}, ${time}`;
};


export const isImageFile = (file: File): boolean =>{ 
  return file.type.startsWith('image/');
}

export const snakeCaseToCamelCase = (str: string): string => {
  return str
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
};