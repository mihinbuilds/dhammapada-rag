"use client";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { SEVERITY_META } from "@/lib/layers";
import type { WarningOut } from "@/lib/api";

function WarningRow({ w }: { w: WarningOut }) {
  const meta = SEVERITY_META[w.severity];
  return (
    <div className={`rounded-lg border px-3.5 py-2.5 grid grid-cols-[auto_1fr] gap-2.5 items-baseline text-sm ${meta.box}`}>
      <span className={`font-mono text-[0.63rem] font-bold uppercase tracking-wide whitespace-nowrap ${meta.code}`}>
        {w.code}
      </span>
      <span className="font-sans text-[0.81rem] leading-snug">
        claim {w.claim_index}: {w.message}
      </span>
    </div>
  );
}

export function WarningList({ warnings }: { warnings: WarningOut[] }) {
  if (!warnings.length) return null;
  const errors = warnings.filter((w) => w.severity === "error");
  const others = warnings.filter((w) => w.severity !== "error");

  return (
    <div className="space-y-3">
      {errors.length > 0 && (
        <div>
          <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint mb-1.5">
            Provenance errors ({errors.length}) — citations that cannot be trusted
          </p>
          <div className="space-y-1.5">
            {errors.map((w, i) => (
              <WarningRow key={i} w={w} />
            ))}
          </div>
        </div>
      )}
      {others.length > 0 && (
        <Accordion type="single" collapsible>
          <AccordionItem value="others">
            <AccordionTrigger className="text-[0.78rem] text-ink-soft normal-case font-medium">
              Format warnings and info ({others.length}) — resolvable, not hallucinations
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-1.5">
                {others.map((w, i) => (
                  <WarningRow key={i} w={w} />
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}
    </div>
  );
}
