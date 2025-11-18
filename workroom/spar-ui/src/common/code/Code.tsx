import { ComponentProps, FC, useMemo } from 'react';
import { Code as BaseCode } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

import { json } from '@codemirror/lang-json';
import { python } from '@codemirror/lang-python';
import { sql } from '@codemirror/lang-sql';

export const SUPPORTED_CODE_MODES = ['python', 'json'] as const;

export interface CodeProps extends Omit<ComponentProps<typeof BaseCode>, 'extensions' | 'ref'> {
  lang?: string;
  maxHeight?: number;
}

const CodeStyled = styled(BaseCode)`
  min-height: 44px;
`;

export const Code: FC<CodeProps> = ({ lang = 'raw', ...restProps }) => {
  const extensions = useMemo(() => {
    const extensionList = [];

    switch (lang) {
      case 'python':
        extensionList.push(python());
        break;
      case 'json':
        extensionList.push(json());
        break;
      case 'sql':
        extensionList.push(sql());
        break;
      default:
        break;
    }

    return extensionList;
  }, [lang]);

  return <CodeStyled extensions={extensions} lineNumbers={false} aria-labelledby="code" {...restProps} />;
};
