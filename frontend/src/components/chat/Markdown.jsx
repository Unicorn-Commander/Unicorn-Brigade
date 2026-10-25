import { memo } from 'react';
import ReactMarkdown from 'react-markdown';

// Token-styled renderers so agent replies show real markdown (bold, code,
// lists, links) instead of literal ** / ` / - . No typography plugin needed —
// every element is styled here. Links open in a new tab and say so.
const components = {
  p: ({ children }) => <p className="my-1 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-fg-strong">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2 hover:brightness-110">
      {children}
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  ),
  ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h1 className="mb-1 mt-2 text-lead font-semibold text-fg-strong first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-1 mt-2 text-body font-semibold text-fg-strong first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-0.5 mt-1.5 text-body font-semibold text-fg-strong first:mt-0">{children}</h3>,
  blockquote: ({ children }) => <blockquote className="my-1 border-l-2 border-border pl-2 text-muted">{children}</blockquote>,
  hr: () => <hr className="my-2 border-border" />,
  code: ({ inline, children }) =>
    inline ? (
      <code className="rounded-chip bg-surface px-1 py-0.5 font-mono text-[0.85em] text-info">{children}</code>
    ) : (
      <code className="font-mono text-[0.85em] text-fg">{children}</code>
    ),
  pre: ({ children }) => (
    <pre className="my-1 overflow-x-auto rounded-control border border-border bg-surface p-2 text-caption leading-snug">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="my-1 overflow-x-auto">
      <table className="border-collapse text-caption">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-border px-2 py-1">{children}</td>,
};

function MarkdownBase({ children }) {
  return <ReactMarkdown components={components}>{children || ''}</ReactMarkdown>;
}

export default memo(MarkdownBase);
