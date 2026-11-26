import { useLayoutEffect, useRef, type ReactNode } from 'react';
import { Button } from './Button';

export function ConfirmationDialog({ title, children, confirmLabel, onCancel, onConfirm, disabled, returnFocus }: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
  disabled?: boolean;
  returnFocus: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const restore = useRef(returnFocus);

  useLayoutEffect(() => {
    const element = dialog.current!;
    if (typeof element.showModal === 'function') element.showModal();
    else element.setAttribute('open', '');
    cancel.current?.focus();
    return () => {
      if (typeof element.close === 'function') element.close();
      restore.current();
    };
  }, []);

  return <dialog ref={dialog} aria-modal="true" aria-labelledby="confirmation-title" aria-describedby="confirmation-description"
    className="m-auto w-[calc(100%-2rem)] max-w-lg rounded-xl border border-divider bg-panel p-4 text-fg backdrop:bg-canvas/80 sm:p-6"
    onCancel={event => { event.preventDefault(); onCancel(); }}>
    <h2 id="confirmation-title" className="text-section">{title}</h2>
    <div id="confirmation-description" className="mt-2 text-support text-fg-secondary [overflow-wrap:anywhere]">{children}</div>
    <div className="mt-5 flex flex-wrap gap-3">
      <button ref={cancel} type="button" onClick={onCancel}
        className="control-target control-focus rounded-lg border border-control-border bg-action-secondary px-4 text-control hover:bg-action-secondary-hover">
        Cancel
      </button>
      <Button variant="destructive" disabled={disabled} onClick={onConfirm}>{confirmLabel}</Button>
    </div>
  </dialog>;
}
