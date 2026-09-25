"use client";

import { useEffect, useState } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { api, type HealthResponse } from "@/lib/api";

type Status = "checking" | "ok" | "down";

export function HealthBadge() {
  const [status, setStatus] = useState<Status>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const h = await api.health();
        if (!cancelled) {
          setHealth(h);
          setStatus("ok");
        }
      } catch {
        if (!cancelled) setStatus("down");
      }
    }
    check();
    const interval = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const dotColor =
    status === "ok" ? "bg-synthesis" : status === "down" ? "bg-error" : "bg-ink-faint";

  const label =
    status === "ok" && health
      ? `API connected — ${health.n_chunks} chunks · ${health.n_verses} verses · ${health.n_stories} stories`
      : status === "down"
        ? "API unreachable — start uvicorn dhammapada_rag.api.main:app"
        : "Checking API…";

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-1 text-[0.68rem] font-mono text-ink-faint">
          <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
          API
        </span>
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}
