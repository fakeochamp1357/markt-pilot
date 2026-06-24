import { useEffect } from 'react';
import { X } from 'lucide-react';
import clsx from 'clsx';

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  /** Maximale Höhe des Sheets (default: 90vh). */
  maxHeight?: string;
}

export function BottomSheet({ open, onClose, title, children, maxHeight = '90vh' }: BottomSheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Schließen"
        className="absolute inset-0 bg-black/40 animate-fadeIn"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={clsx(
          'relative w-full bg-white rounded-t-2xl sm:rounded-2xl sm:max-w-lg shadow-sheet',
          'flex flex-col animate-slideUp',
        )}
        style={{ maxHeight }}
      >
        <div className="flex items-center justify-between px-4 pt-3 pb-2 border-b border-gray-100">
          <h2 className="text-lg font-bold text-ink-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Schließen"
            className="tap rounded-full hover:bg-gray-100"
          >
            <X size={22} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3">{children}</div>
      </div>
    </div>
  );
}