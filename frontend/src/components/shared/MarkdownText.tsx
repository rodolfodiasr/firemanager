import React from "react";

interface Props {
  content: string;
  className?: string;
}

// Minimal markdown renderer — handles the subset Claude uses in investigation analyses
export function MarkdownText({ content, className = "" }: Props) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {renderBlocks(content)}
    </div>
  );
}

// ── Inline formatting ─────────────────────────────────────────────────────────

function renderInline(text: string): React.ReactNode {
  const segments: React.ReactNode[] = [];
  let rest = text;
  let k = 0;

  while (rest.length > 0) {
    // Bold (**text**)
    const bm = rest.match(/^([\s\S]*?)\*\*(.+?)\*\*([\s\S]*)/);
    // Inline code (`code`)
    const cm = rest.match(/^([\s\S]*?)`([^`]+)`([\s\S]*)/);

    const bFirst = bm ? bm[1].length : Infinity;
    const cFirst = cm ? cm[1].length : Infinity;

    if (bm && bFirst <= cFirst) {
      if (bm[1]) segments.push(<React.Fragment key={k++}>{bm[1]}</React.Fragment>);
      segments.push(<strong key={k++} className="font-semibold text-gray-800">{bm[2]}</strong>);
      rest = bm[3];
    } else if (cm) {
      if (cm[1]) segments.push(<React.Fragment key={k++}>{cm[1]}</React.Fragment>);
      segments.push(
        <code key={k++} className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-[11px] font-mono">
          {cm[2]}
        </code>
      );
      rest = cm[3];
    } else {
      segments.push(<React.Fragment key={k++}>{rest}</React.Fragment>);
      break;
    }
  }

  return segments.length === 1 ? segments[0] : <>{segments}</>;
}

// ── Table ─────────────────────────────────────────────────────────────────────

function parseTableLines(lines: string[]): React.ReactNode {
  const rows = lines
    .map((l) => l.split("|").slice(1, -1).map((c) => c.trim()))
    .filter((row) => !row.every((c) => /^:?-+:?$/.test(c)));

  if (rows.length === 0) return null;
  const [head, ...body] = rows;

  return (
    <div className="overflow-x-auto my-1">
      <table className="text-xs border-collapse min-w-full">
        <thead>
          <tr>
            {head.map((h, j) => (
              <th key={j} className="text-left px-2 py-1.5 bg-gray-100 border border-gray-200 font-semibold text-gray-700 whitespace-nowrap">
                {renderInline(h)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50/60"}>
              {row.map((cell, j) => (
                <td key={j} className="px-2 py-1.5 border border-gray-200 text-gray-600 align-top">
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Block parser ──────────────────────────────────────────────────────────────

function renderBlocks(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    // Fenced code block
    if (trimmed.startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <pre key={nodes.length} className="bg-gray-900 text-gray-100 rounded-lg p-3 text-xs font-mono overflow-x-auto my-2 whitespace-pre-wrap break-all">
          {codeLines.join("\n")}
        </pre>
      );
      i++; // skip closing ```
      continue;
    }

    // Table (line with | chars)
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i]);
        i++;
      }
      const tbl = parseTableLines(tableLines);
      if (tbl) nodes.push(<React.Fragment key={nodes.length}>{tbl}</React.Fragment>);
      continue;
    }

    // Horizontal rule
    if (/^[-*_]{3,}$/.test(trimmed)) {
      nodes.push(<hr key={nodes.length} className="border-gray-200 my-2" />);
      i++;
      continue;
    }

    // Headings
    const h3m = trimmed.match(/^### (.+)/);
    const h2m = trimmed.match(/^## (.+)/);
    const h1m = trimmed.match(/^# (.+)/);
    if (h1m) {
      nodes.push(<p key={nodes.length} className="text-[13px] font-bold text-gray-800 mt-2 mb-0.5">{renderInline(h1m[1])}</p>);
      i++; continue;
    }
    if (h2m) {
      nodes.push(<p key={nodes.length} className="text-xs font-bold text-gray-700 mt-2 mb-0.5">{renderInline(h2m[1])}</p>);
      i++; continue;
    }
    if (h3m) {
      nodes.push(<p key={nodes.length} className="text-xs font-semibold text-gray-700 mt-1.5">{renderInline(h3m[1])}</p>);
      i++; continue;
    }

    // Bullet / ordered list — collect contiguous items
    const bulletRe = /^[-*•] (.+)/;
    const orderedRe = /^\d+\. (.+)/;
    if (bulletRe.test(trimmed) || orderedRe.test(trimmed)) {
      const isOrdered = orderedRe.test(trimmed);
      const items: string[] = [];
      while (i < lines.length && (bulletRe.test(lines[i].trim()) || orderedRe.test(lines[i].trim()))) {
        const m = lines[i].trim().match(bulletRe) ?? lines[i].trim().match(orderedRe);
        if (m) items.push(m[1]);
        i++;
      }
      if (isOrdered) {
        nodes.push(
          <ol key={nodes.length} className="list-decimal list-inside space-y-0.5 pl-1">
            {items.map((t, j) => <li key={j} className="text-xs text-gray-700 leading-relaxed">{renderInline(t)}</li>)}
          </ol>
        );
      } else {
        nodes.push(
          <ul key={nodes.length} className="space-y-0.5">
            {items.map((t, j) => (
              <li key={j} className="flex gap-1.5 text-xs text-gray-700 leading-relaxed">
                <span className="text-brand-500 shrink-0 mt-0.5">•</span>
                <span>{renderInline(t)}</span>
              </li>
            ))}
          </ul>
        );
      }
      continue;
    }

    // Empty line — skip
    if (trimmed === "") { i++; continue; }

    // Regular paragraph
    nodes.push(
      <p key={nodes.length} className="text-xs text-gray-700 leading-relaxed">
        {renderInline(trimmed)}
      </p>
    );
    i++;
  }

  return nodes;
}
