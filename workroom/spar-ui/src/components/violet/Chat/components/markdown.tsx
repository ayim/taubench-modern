import { MarkdownParserRules } from '@sema4ai/components';

import { Code } from '../../../../common/code';
import { InteractionComponent } from './interactionComponents';
import { Chart } from './interactionComponents/chart';
import { Table } from './markdownComponents/Table';
import { InlineHTML } from './markdownComponents/InlineHTML';
import { ChartInlineMount } from './markdownComponents/InlineChartMount';
import { ButtonsInlineMount } from './markdownComponents/ButtonsInlineMount';
import { InlineDataFrameMount } from './markdownComponents/InlineDataFrameMount';
import type { ButtonAction } from './markdownComponents/ButtonsInlineMount';

type InlineWidgetBase = {
  id?: string;
  widget_id?: string | null;
  description?: string | null;
  status?: string;
  error?: string | null;
  thinking?: string | null;
};

type ChartWidgetResult = {
  spec?: unknown;
  chart_spec?: unknown;
  _chart_spec?: unknown;
  chart_spec_raw?: string;
  sub_type?: string;
  [key: string]: unknown;
};

export type InlineWidget =
  | (InlineWidgetBase & {
      kind: 'chart';
      result?: ChartWidgetResult;
    })
  | (InlineWidgetBase & {
      kind: 'buttons';
      actions?: ButtonAction[];
      result?: unknown;
    });

const parseChartAttrs = (raw: string): { id?: string; description?: string } => {
  const idMatch = raw.match(/id\s*=\s*["']([^"']+)["']/i);
  const descMatch = raw.match(/description\s*=\s*["']([^"']+)["']/i);
  return { id: idMatch?.[1], description: descMatch?.[1] };
};

const isChartTag = (text: string) => text.trim().toLowerCase().startsWith('<chart');
const isButtonsTag = (text: string) => text.trim().toLowerCase().startsWith('<buttons');
const isDataFrameTag = (text: string) => text.trim().toLowerCase().startsWith('<dataframe');

const parseDataFrameAttrs = (raw: string): { name?: string; cols?: string[]; rows?: number } => {
  const nameMatch = raw.match(/name\s*=\s*["']([^"']+)["']/i);
  const colsMatch = raw.match(/cols\s*=\s*["']([^"']+)["']/i);
  const rowsMatch = raw.match(/rows\s*=\s*["']([^"']+)["']/i);

  const cols = colsMatch?.[1]
    ?.split(',')
    .map((c) => c.trim())
    .filter(Boolean);

  const rowsRaw = rowsMatch?.[1];
  const rowsNum = rowsRaw ? Number.parseInt(rowsRaw, 10) : undefined;

  return {
    name: nameMatch?.[1],
    cols,
    rows: Number.isFinite(rowsNum) && rowsNum ? rowsNum : undefined,
  };
};

const resolveChartSpec = (widget: InlineWidget & { kind: 'chart' }): { spec: unknown; specRaw?: string } => {
  // eslint-disable-next-line no-underscore-dangle
  const inlineSpec = widget.result?._chart_spec;
  const spec = widget.result?.spec ?? widget.result?.chart_spec ?? inlineSpec ?? widget.result;
  const specRaw = widget.result?.chart_spec_raw || (spec ? JSON.stringify(spec) : undefined);
  return { spec, specRaw };
};

const resolveButtonActions = (widget: InlineWidget | undefined): ButtonAction[] => {
  if (!widget) {
    return [];
  }
  if (widget.kind === 'buttons' && widget.actions) {
    return widget.actions;
  }
  if (Array.isArray(widget.result)) {
    return widget.result as ButtonAction[];
  }
  return [];
};

export const createMarkdownRules = (
  inlineWidgets: InlineWidget[] | undefined,
  baseMessageId?: string,
): MarkdownParserRules => {
  const widgets = inlineWidgets ?? [];
  return {
    paragraph: (key, token, parseContent, msgId, streaming) => {
      const children = parseContent(key, token.tokens, msgId, streaming);
      const raw = token.raw?.toLowerCase() ?? '';
      const hasInlineWidget = raw.includes('<chart') || raw.includes('<buttons') || raw.includes('<dataframe');
      if (hasInlineWidget) {
        return (
          <div key={key} style={{ display: 'contents' }}>
            {children}
          </div>
        );
      }
      return <p key={key}>{children}</p>;
    },
    code: (key, tokens, _, currentMessageId) => {
      if (tokens.lang && 'sema4-json'.indexOf(tokens.lang) === 0) {
        return <InteractionComponent key={key} content={tokens.text} messageId={currentMessageId} />;
      }

      if (tokens.lang && 'vega-lite'.indexOf(tokens.lang) === 0) {
        return <Chart key={key} spec={tokens.text} />;
      }

      return <Code key={key} aria-label="Code" lang={tokens.lang} title={tokens.lang} value={tokens.text} rows={10} />;
    },
    codespan: (key, token) => {
      const text = token.text || '';
      const lower = text.trim().toLowerCase();

      if (isChartTag(lower)) {
        const { id, description } = parseChartAttrs(text);
        const widget = widgets.find((w) => (w.id || w.widget_id) === id);
        if (!widget || widget.kind !== 'chart') {
          return <code key={key}>{text}</code>;
        }
        const { specRaw } = resolveChartSpec(widget);
        const fallbackDescription = description ?? widget.description ?? undefined;
        const fallbackError = widget.error ?? undefined;
        const fallbackThinking = widget.thinking ?? undefined;
        return (
          <ChartInlineMount
            key={key}
            spec={specRaw}
            status={(widget?.status as string | undefined) ?? 'loading'}
            description={fallbackDescription}
            error={fallbackError}
            thinking={fallbackThinking}
          />
        );
      }

      if (isButtonsTag(lower)) {
        const { id, description } = parseChartAttrs(text);
        const widget = widgets.find((w) => (w.id || w.widget_id) === id);
        const actions = resolveButtonActions(widget);
        const fallbackDescription = description ?? widget?.description ?? undefined;
        const fallbackError = widget?.error ?? undefined;
        const fallbackThinking = widget?.thinking ?? undefined;
        return (
          <ButtonsInlineMount
            key={key}
            status={(widget?.status as string | undefined) ?? 'loading'}
            description={fallbackDescription}
            error={fallbackError}
            thinking={fallbackThinking ?? undefined}
            actions={actions || []}
            messageId={baseMessageId}
          />
        );
      }

      if (isDataFrameTag(lower)) {
        const { name, cols, rows } = parseDataFrameAttrs(text);
        return <InlineDataFrameMount key={key} name={name} columns={cols} rows={rows} />;
      }

      return <code key={key}>{text}</code>;
    },
    table: (key, { header, rows, raw }, parseContent, currentMessageId, streaming) => {
      const columns = header.map((column) => ({
        id: column.text,
        title: column.text,
      }));

      const data = rows.map((row) => {
        return Object.fromEntries(
          columns.map((column, index) => [
            column.id,
            parseContent(key, row[index].tokens, currentMessageId, streaming),
          ]),
        );
      });

      return <Table key={key} columns={columns} data={data} raw={raw} />;
    },

    html: (key, { raw }) => {
      const trimmed = raw.trim();
      if (trimmed.toLowerCase().startsWith('<chart')) {
        const { id, description } = parseChartAttrs(trimmed);
        const widget = widgets.find((w) => (w.id || w.widget_id) === id);
        if (!widget || widget.kind !== 'chart') {
          return <InlineHTML key={key} content={raw} />;
        }
        const { specRaw } = resolveChartSpec(widget);

        const fallbackDescription = description ?? widget?.description ?? undefined;
        const fallbackError = widget?.error ?? undefined;
        const fallbackThinking = widget?.thinking ?? undefined;
        return (
          <ChartInlineMount
            key={key}
            spec={specRaw}
            status={(widget?.status as string | undefined) ?? 'loading'}
            description={fallbackDescription}
            error={fallbackError}
            thinking={fallbackThinking}
          />
        );
      }

      if (trimmed.toLowerCase().startsWith('<buttons')) {
        const { id, description } = parseChartAttrs(trimmed);
        const widget = widgets.find((w) => (w.id || w.widget_id) === id);
        const actions = resolveButtonActions(widget);
        const fallbackDescription = description ?? widget?.description ?? undefined;
        const fallbackError = widget?.error ?? undefined;
        const fallbackThinking = widget?.thinking ?? undefined;
        return (
          <ButtonsInlineMount
            key={key}
            status={(widget?.status as string | undefined) ?? 'loading'}
            description={fallbackDescription}
            error={fallbackError}
            thinking={fallbackThinking ?? undefined}
            actions={actions || []}
            messageId={baseMessageId}
          />
        );
      }

      if (trimmed.toLowerCase().startsWith('<dataframe')) {
        const { name, cols, rows } = parseDataFrameAttrs(trimmed);
        return <InlineDataFrameMount key={key} name={name} columns={cols} rows={rows} />;
      }

      return <InlineHTML key={key} content={raw} />;
    },
  };
};
