import { MarkdownParserRules } from '@sema4ai/components';

import { Code } from '../../../common/code';
import { InteractionComponent } from './interactionComponents';
import { Chart } from './interactionComponents/chart';
import { Table } from './markdownComponents/Table';

export const markdownRules: MarkdownParserRules = {
  code: (tokens, _, messageId) => {
    if (tokens.lang && 'sema4-json'.indexOf(tokens.lang) === 0) {
      return <InteractionComponent content={tokens.text} messageId={messageId} />;
    }

    if (tokens.lang && 'vega-lite'.indexOf(tokens.lang) === 0) {
      return <Chart spec={tokens.text} />;
    }

    return <Code aria-label="Code" lang={tokens.lang} value={tokens.text} />;
  },
  table: Table,
};
