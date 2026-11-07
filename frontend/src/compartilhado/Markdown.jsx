import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Elementos do Markdown com o visual do sistema (tabelas rolam na horizontal, listas compactas). */
const elementosMarkdown = {
  table: (props) => (
    <div className="my-2 overflow-x-auto rounded border border-line">
      <table className="w-full border-collapse text-left text-[13px]" {...props} />
    </div>
  ),
  th: (props) => <th className="border border-line bg-paper px-2 py-1.5 font-semibold" {...props} />,
  td: (props) => <td className="border border-line px-2 py-1.5 align-top" {...props} />,
  p: (props) => <p className="my-1.5 first:mt-0 last:mb-0" {...props} />,
  ul: (props) => <ul className="my-1.5 list-disc space-y-0.5 pl-5" {...props} />,
  ol: (props) => <ol className="my-1.5 list-decimal space-y-0.5 pl-5" {...props} />,
  h1: (props) => <h3 className="mb-1 mt-3 text-base font-semibold" {...props} />,
  h2: (props) => <h3 className="mb-1 mt-3 text-base font-semibold" {...props} />,
  h3: (props) => <h4 className="mb-1 mt-2 text-[15px] font-semibold" {...props} />,
  strong: (props) => <strong className="font-semibold" {...props} />,
  a: (props) => <a className="text-canopy underline" target="_blank" rel="noreferrer" {...props} />,
}

export default function Markdown({ children }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={elementosMarkdown}>
      {children}
    </ReactMarkdown>
  )
}
