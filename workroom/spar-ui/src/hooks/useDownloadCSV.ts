import { useState } from 'react';

class StreamWriter {
  private headers: string[];

  private chunks: string[] = [];

  /**
   * Current size in bytes
   */
  private currentSize: number = 0;

  /**
   * Max size in bytes
   */
  private maxSize: number | null;

  constructor(headers: string[], maxSize?: number | null) {
    this.headers = headers;
    this.maxSize = maxSize ?? null;

    // Add headers as first chunk
    const headerRow = StreamWriter.formatRow(headers);
    this.chunks.push(headerRow);
    this.currentSize += new Blob([headerRow]).size;
  }

  private static formatRow(values: unknown[]): string {
    const escaped = values.map((val) => {
      const str = val == null ? '' : String(val);
      // Escape quotes and wrap in quotes if contains comma, quote, or newline
      if (str.includes(',') || str.includes('"') || str.includes('\n')) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    });
    return `${escaped.join(',')}\n`;
  }

  addRows(rows: Record<string, unknown>[]): { limitReached: boolean } {
    let limitReached = false;

    // eslint-disable-next-line no-restricted-syntax
    for (const row of rows) {
      if (this.maxSize !== null && this.currentSize >= this.maxSize) {
        limitReached = true;
        break;
      }

      const values = this.headers.map((header) => row[header]);
      const csvRow = StreamWriter.formatRow(values);
      const rowSize = new Blob([csvRow]).size;

      this.chunks.push(csvRow);
      this.currentSize += rowSize;
    }

    return { limitReached };
  }

  download(filename: string): void {
    const blob = new Blob(this.chunks, { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }
}

interface Props {
  headers: string[];
  fetchChunk: () => Promise<{ hasNextChunk: boolean; data: Record<string, unknown>[] }>;
  filename: string;
  maxSize?: number;
}

export function useDownloadCSV({ headers, fetchChunk, filename, maxSize }: Props) {
  const [isDownloading, setIsDownloading] = useState(false);

  const downloadChunks = async (writer: StreamWriter) => {
    try {
      const { hasNextChunk, data } = await fetchChunk();
      const { limitReached } = writer.addRows(data);

      if (!limitReached && hasNextChunk) {
        return await downloadChunks(writer);
      }

      writer.download(filename);
      setIsDownloading(false);
      return { success: true };
    } catch {
      setIsDownloading(false);
      return { success: false };
    }
  };

  const startDownload = async () => {
    setIsDownloading(true);

    const writer = new StreamWriter(headers, maxSize);
    const result = await downloadChunks(writer);
    return result;
  };

  return {
    startDownload,
    isDownloading,
  };
}
