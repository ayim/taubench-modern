import { useState } from 'react';
import * as yaml from 'js-yaml';
import { Copy, Eye, EyeOff } from 'lucide-react';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneLight } from 'react-syntax-highlighter/dist/esm/styles/prism';
import yamlLanguage from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';

interface JsonYamlFormatterProps {
  content: string;
  label?: string;
  maxHeight?: string;
  defaultExpanded?: boolean;
}

// Register YAML language for syntax highlighting
SyntaxHighlighter.registerLanguage('yaml', yamlLanguage);

export function JsonYamlFormatter({
  content,
  label = 'Data',
  maxHeight = 'max-h-32',
  defaultExpanded = false,
}: JsonYamlFormatterProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  // Try to parse as JSON and convert to YAML
  const formatContent = () => {
    try {
      const parsed = JSON.parse(content);

      // Create a custom YAML dumper with better string handling
      const yamlContent = yaml.dump(parsed, {
        indent: 2,
        lineWidth: 80,
        noRefs: true,
        sortKeys: false,
        flowLevel: -1, // Always use block style
        styles: {
          '!!str': 'literal', // Use literal style for multiline strings
        },
        replacer: (_key: string, value: any) => {
          // For very long strings, truncate in the middle but preserve structure
          if (typeof value === 'string' && value.length > 2000) {
            const start = value.substring(0, 500);
            const end = value.substring(value.length - 500);
            return `${start}\n\n... [${value.length - 1000} characters truncated] ...\n\n${end}`;
          }
          return value;
        },
      });

      return { formatted: yamlContent, language: 'yaml', isParsed: true };
    } catch {
      // If not valid JSON, return as-is
      return { formatted: content, language: 'text', isParsed: false };
    }
  };

  const { formatted, isParsed } = formatContent();

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy to clipboard:', err);
    }
  };

  const isLarge = formatted.length > 500 || formatted.split('\n').length > 10;
  const shouldTruncate = isLarge && !isExpanded;

  const displayContent = shouldTruncate ? formatted.split('\n').slice(0, 8).join('\n') + '\n...' : formatted;

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs font-medium text-gray-600">
          {label}
          {isParsed && <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-sm text-xs">YAML</span>}
        </div>
        <div className="flex items-center space-x-1">
          {isLarge && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center space-x-1 text-xs text-gray-500 hover:text-gray-700 px-1.5 py-0.5 rounded-sm hover:bg-gray-100"
            >
              {isExpanded ? (
                <>
                  <EyeOff className="h-3 w-3" />
                  <span>Collapse</span>
                </>
              ) : (
                <>
                  <Eye className="h-3 w-3" />
                  <span>Expand</span>
                </>
              )}
            </button>
          )}
          <button
            onClick={handleCopy}
            className="flex items-center space-x-1 text-xs text-gray-500 hover:text-gray-700 px-1.5 py-0.5 rounded-sm hover:bg-gray-100"
          >
            <Copy className="h-3 w-3" />
            <span>{copied ? 'Copied!' : 'Copy'}</span>
          </button>
        </div>
      </div>

      <div
        className={`bg-white rounded-sm border overflow-hidden ${shouldTruncate ? maxHeight : 'max-h-96'} overflow-y-auto`}
      >
        {isParsed ? (
          <SyntaxHighlighter
            language="yaml"
            style={oneLight}
            customStyle={{
              margin: 0,
              padding: '8px',
              background: 'transparent',
              fontSize: '11px',
              lineHeight: '1.4',
            }}
            wrapLongLines={true}
          >
            {displayContent}
          </SyntaxHighlighter>
        ) : (
          <pre className="p-2 whitespace-pre-wrap text-xs font-mono bg-gray-50">
            <code>{displayContent}</code>
          </pre>
        )}
      </div>

      {shouldTruncate && (
        <div className="absolute bottom-0 left-0 right-0 h-6 bg-linear-to-t from-white to-transparent pointer-events-none rounded-b" />
      )}
    </div>
  );
}
