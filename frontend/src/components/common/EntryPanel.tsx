import type { ReactNode } from 'react';
import { SectionCard } from './SectionCard';

export function EntryPanel({ title, children }: { title: string; children: ReactNode }) {
  return <section aria-labelledby="entry-title" className="mx-auto max-w-[600px] py-4 sm:py-8">
    <SectionCard className="space-y-4 [overflow-wrap:anywhere]">
      <h1 id="entry-title" className="text-page text-fg md:text-page-wide">{title}</h1>
      {children}
    </SectionCard>
  </section>;
}

export const entryLink = 'control-target control-focus inline-flex max-w-full items-center justify-center rounded-lg border border-control-border px-3 py-1.5 text-control text-link hover:bg-panel-raised';
export const entryAlert = 'rounded-lg border border-risk-medium/35 bg-risk-medium-bg p-3 text-support text-risk-medium';
