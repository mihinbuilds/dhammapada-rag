import { LAYER_META, LAYER_ORDER } from "@/lib/layers";
import type { AnswerResponse } from "@/lib/api";

export function AnswerSummary({ result }: { result: AnswerResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rounded-full border border-line bg-surface px-2.5 py-1 font-mono text-[0.69rem] text-ink-faint">
        {result.model}
      </span>
      <span className="rounded-full border border-line bg-surface px-2.5 py-1 font-mono text-[0.69rem] text-ink-faint">
        {result.latency_s.toFixed(1)}s
      </span>
      <span className="rounded-full border border-line bg-surface px-2.5 py-1 font-mono text-[0.69rem] text-ink-faint">
        ~{result.prompt_tokens} / {result.num_ctx} tok
      </span>
      {LAYER_ORDER.map((layer) => {
        const meta = LAYER_META[layer];
        return (
          <span
            key={layer}
            className={`rounded-full border px-2.5 py-1 font-mono text-[0.69rem] ${meta.badge}`}
          >
            {meta.label.toLowerCase()} {result.layer_counts[layer]}
          </span>
        );
      })}
    </div>
  );
}
