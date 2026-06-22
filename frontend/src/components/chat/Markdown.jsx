import { memo } from 'react';
import ReactMarkdown from 'react-markdown';

// Tailwind-styled renderers so agent replies show real markdown (bold, code,
// lists, links) instead of literal ** / ` / - . No typography plugin needed —
// every element is styled inline. Links open safely in a new tab.
const components = {
  p: ({ children }) => <p className="my-1 first:mt-0 last:mb-0 leading-relaxed">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-unicorn-300 underline underline-offset-2 hover:text-unicorn-200">
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="my-1 ml-4 list-disc space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="my-1 ml-4 list-decimal space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  h1: ({ children }) => <h1 className="mb-1 mt-2 text-base font-semibold text-white first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mb-1 mt-2 text-sm font-semibold text-white first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mb-0.5 mt-1.5 text-sm font-semibold text-slate-100 first:mt-0">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="my-1 border-l-2 border-slate-600 pl-2 text-slate-300">{children}</blockquote>
  ),
  hr: () => <hr className="my-2 border-slate-700" />,
  code: ({ inline, children }) =>
    inline ? (
      <code className="rounded bg-slate-900/70 px-1 py-0.5 font-mono text-[0.82em] text-cyan-200">{children}</code>
    ) : (
      <code className="font-mono text-[0.82em] text-cyan-100">{children}</code>
    ),
  pre: ({ children }) => (
    <pre className="my-1 overflow-x-auto rounded-lg bg-slate-900/80 p-2 text-[12px] leading-snug">{children}</pre>
  ),
  table: ({ children }) => (
    <div className="my-1 overflow-x-auto">
      <table className="border-collapse text-xs">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-slate-700 px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-slate-700 px-2 py-1">{children}</td>,
};

function MarkdownBase({ children }) {
  return <ReactMarkdown components={components}>{children || ''}</ReactMarkdown>;
}

export default memo(MarkdownBase);
