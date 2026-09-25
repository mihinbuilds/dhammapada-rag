import { EvalTable } from "@/components/eval-table";
import { CopyButton } from "@/components/copy-button";
import { LAYER_META, LAYER_ORDER, SEVERITY_META } from "@/lib/layers";

const GITHUB_HANDLE = "mihinXL";

const CITATION = `@software{dhammapada_rag_2026,
  title = {Dhammapada-RAG: Layer-Attributed Retrieval-Augmented Generation
           over the Dhammapada and its Commentary},
  year  = {2026},
  url   = {https://github.com/${GITHUB_HANDLE}/dhammapada-rag}
}`;

export default function MethodPage() {
  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-10 sm:py-14">
      <header className="border-b-2 border-ink pb-6 mb-8">
        <p className="font-mono text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-ink-faint mb-2">
          Reference
        </p>
        <h1 className="font-serif-display text-[1.9rem] sm:text-[2.3rem] font-bold leading-[1.12] text-ink max-w-3xl">
          Method & notes
        </h1>
      </header>

      <div className="space-y-12">
        <section className="space-y-3">
          <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
            Layer taxonomy
          </p>
          <div className="space-y-2.5">
            {LAYER_ORDER.map((layer) => {
              const meta = LAYER_META[layer];
              return (
                <div key={layer} className={`rounded-lg border p-4 ${meta.badge}`} style={{ borderLeftWidth: 3 }}>
                  <div className="flex items-center justify-between gap-3 mb-1.5">
                    <span
                      className={`inline-flex items-center rounded-[3px] px-1.5 py-0.5 text-[0.59rem] font-sans font-bold uppercase tracking-wide text-white ${meta.dot}`}
                    >
                      {meta.label}
                    </span>
                    <span className="font-mono text-[0.69rem] text-ink-soft">{layer}</span>
                  </div>
                  <p className="font-serif text-[0.94rem] leading-relaxed text-ink">{meta.desc}</p>
                </div>
              );
            })}
          </div>
          <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
            The schema deliberately has no free-text summary field: an untagged paragraph is the
            escape hatch a conflated claim would slip through. Readable prose is composed
            client-side from tagged claims only.
          </p>
        </section>

        <section className="space-y-3">
          <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
            Provenance audit
          </p>
          <EvalTable
            columns={[{ header: "Severity" }, { header: "Meaning" }, { header: "Treatment" }]}
            rows={[
              ["error", SEVERITY_META.error.label, "Shown inline, red"],
              ["warning", SEVERITY_META.warning.label, "Grouped, amber"],
              ["info", SEVERITY_META.info.label, "Grouped, blue"],
            ]}
          />
        </section>

        <section className="space-y-3">
          <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
            Known limitations
          </p>
          <ul className="space-y-2 font-serif text-[0.94rem] leading-relaxed text-ink list-disc pl-5">
            <li>
              Evaluation is <strong>single-annotator</strong>; no inter-annotator agreement is
              claimed.
            </li>
            <li>
              <strong>Alignment questions</strong> are the hardest retrieval class: their gold
              source is the commentary&apos;s own grouping.
            </li>
            <li>
              <strong>Synthesis is under-used</strong> by the generator (high precision, low
              recall).
            </li>
            <li>
              <strong>Retries do not substitute for capacity</strong>: clean rate improves with
              model size.
            </li>
            <li>
              <strong>Story grouping has a single witness</strong> (Ānandajoti 2024); no
              independent edition cross-checks it.
            </li>
          </ul>
        </section>

        <section className="space-y-3">
          <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
            Data & licenses
          </p>
          <EvalTable
            columns={[{ header: "Layer" }, { header: "Source" }, { header: "License" }]}
            rows={[
              ["Pali verse", "Mahāsaṅgīti (via SuttaCentral)", "CC0"],
              ["English verse", "Bhikkhu Sujato (via SuttaCentral)", "CC0"],
              ["Interlinear gloss", "Ānandajoti Bhikkhu, 2017", "CC BY-SA 3.0"],
              ["Commentary & grouping", "Ānandajoti's revision of Burlingame, 2024", "see PROVENANCE.md"],
            ]}
          />
          <p className="font-sans text-[0.78rem] leading-relaxed text-ink-faint">
            CC BY-SA 3.0 propagates: any file derived from the interlinear edition must carry a
            compatible license. Per-file terms: docs/licensing.md.
          </p>
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
              Citation
            </p>
            <CopyButton text={CITATION} />
          </div>
          <pre className="rounded-lg border border-line bg-surface-2 p-4 overflow-x-auto font-mono text-[0.76rem] leading-relaxed text-ink">
            {CITATION}
          </pre>
        </section>
      </div>
    </div>
  );
}
