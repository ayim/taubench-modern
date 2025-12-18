import { MarkdownParserRules } from '@sema4ai/components';

import { Code } from '../../../common/code';
import { InteractionComponent } from './interactionComponents';
import { Chart } from './interactionComponents/chart';
import { Table } from './markdownComponents/Table';
import { InlineHTML } from './markdownComponents/InlineHTML';
import { ExtractedDataRenderer } from './markdownComponents/ExtractedDataRenderer';

export const markdownRules: MarkdownParserRules = {
  code: (key, tokens, _, messageId) => {
    if (tokens.lang && 'sema4-json'.indexOf(tokens.lang) === 0) {
      return <InteractionComponent key={key} content={tokens.text} messageId={messageId} />;
    }

    if (tokens.lang && 'vega-lite'.indexOf(tokens.lang) === 0) {
      return <Chart key={key} spec={tokens.text} />;
    }

    return <Code key={key} aria-label="Code" lang={tokens.lang} title={tokens.lang} value={tokens.text} rows={10} />;
  },
  table: (key, { header, rows, raw }, parseContent, messageId, streaming) => {
    const columns = header.map((column) => ({
      id: column.text,
      title: column.text,
    }));

    const data = rows.map((row) => {
      return Object.fromEntries(
        columns.map((column, index) => [column.id, parseContent(key, row[index].tokens, messageId, streaming)]),
      );
    });

    return <Table key={key} columns={columns} data={data} raw={raw} />;
  },

  html: (key, { raw }) => {
    return <InlineHTML key={key} content={raw} />;
  },
};

export const markdownUserMessageRules: MarkdownParserRules = {
  ...markdownRules,
  code: (key, tokens, _, messageId, streaming) => {
    if (tokens.lang && 'sema4di-json'.indexOf(tokens.lang) === 0) {
      try {
        const payload: unknown = JSON.parse(tokens.text);
        return <ExtractedDataRenderer key={key} data={payload} />;
      } catch {
        // fallback to json code block on failure
        return markdownRules.code?.(key, { ...tokens, lang: 'json' }, _, messageId, streaming);
      }
    }

    return markdownRules.code?.(key, tokens, _, messageId, streaming);
  },
};
