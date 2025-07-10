import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings
          h1: ({ children }) => <h1 className="text-lg font-bold mb-2 text-gray-900">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-bold mb-2 text-gray-900">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-bold mb-1 text-gray-900">{children}</h3>,

          // Paragraphs
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,

          // Lists
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-sm">{children}</li>,

          // Code
          code: ({ children, className }) => {
            const isInline = !className;
            if (isInline) {
              return (
                <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono text-gray-800">{children}</code>
              );
            }
            return (
              <code className="block bg-gray-100 p-2 rounded text-xs font-mono text-gray-800 overflow-x-auto">
                {children}
              </code>
            );
          },

          pre: ({ children }) => <pre className="bg-gray-100 p-3 rounded mb-2 overflow-x-auto">{children}</pre>,

          // Links
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 underline"
            >
              {children}
            </a>
          ),

          // Blockquotes
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 pl-3 py-1 mb-2 text-gray-700 italic">
              {children}
            </blockquote>
          ),

          // Strong/Bold
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,

          // Emphasis/Italic
          em: ({ children }) => <em className="italic">{children}</em>,

          // Horizontal rule
          hr: () => <hr className="border-gray-300 my-3" />,

          // Tables
          table: ({ children }) => (
            <div className="overflow-x-auto mb-2">
              <table className="min-w-full border border-gray-300 text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-gray-50">{children}</thead>,
          th: ({ children }) => <th className="border border-gray-300 px-2 py-1 text-left font-medium">{children}</th>,
          td: ({ children }) => <td className="border border-gray-300 px-2 py-1">{children}</td>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
