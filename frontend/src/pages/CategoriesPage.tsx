import { useState } from 'react';
import { Plus, Pencil, Trash2 } from 'lucide-react';
import { BottomSheet } from '@/components/BottomSheet';
import { useMarketData } from '@/hooks/useData';
import { useAppStore } from '@/store';
import {
  cacheCategories,
  enqueueOutbox,
} from '@/db/dexie';
import { createCategory, deleteCategory, listCategories, updateCategory } from '@/api/client';
import { refreshOutboxCountNow } from '@/hooks/useOutboxSync';
import type { Category } from '@/types/api';

const PRESET_COLORS = [
  '#3B82F6', '#10B981', '#F59E0B', '#A16207', '#EF4444',
  '#8B5CF6', '#EC4899', '#14B8A6', '#0EA5E9', '#6B7280',
];

export function CategoriesPage() {
  const { products, categories, refresh } = useMarketData();
  const isOnline = useAppStore((s) => s.isOnline);

  const [editor, setEditor] = useState<Category | 'new' | null>(null);
  const [name, setName] = useState('');
  const [color, setColor] = useState(PRESET_COLORS[0]);
  const [sortOrder, setSortOrder] = useState('0');
  const [submitting, setSubmitting] = useState(false);

  const counts = new Map<number, number>();
  products.forEach((p) => {
    if (p.category_id && p.is_active) counts.set(p.category_id, (counts.get(p.category_id) ?? 0) + 1);
  });

  const openNew = () => {
    setName('');
    setColor(PRESET_COLORS[0]);
    setSortOrder(String(categories.length + 1));
    setEditor('new');
  };
  const openEdit = (c: Category) => {
    setName(c.name);
    setColor(c.color);
    setSortOrder(String(c.sort_order));
    setEditor(c);
  };

  const submit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    try {
      const payload = { name: name.trim(), color, sort_order: parseInt(sortOrder, 10) || 0 };
      if (editor === 'new') {
        if (!isOnline) {
          await enqueueOutbox({ kind: 'category.create', payload });
          await refreshOutboxCountNow();
        } else {
          await createCategory(payload);
        }
      } else if (editor) {
        if (!isOnline) {
          await enqueueOutbox({ kind: 'category.update', id: editor.id, payload });
          await refreshOutboxCountNow();
        } else {
          await updateCategory(editor.id, payload);
        }
      }
      const fresh = await listCategories();
      await cacheCategories(fresh);
      setEditor(null);
      await refresh();
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (c: Category) => {
    if (!window.confirm(`Kategorie "${c.name}" wirklich löschen? Produkte verlieren ihre Zuordnung.`)) return;
    try {
      if (!isOnline) {
        await enqueueOutbox({ kind: 'category.delete', id: c.id });
        await refreshOutboxCountNow();
      } else {
        await deleteCategory(c.id);
      }
      const fresh = await listCategories();
      await cacheCategories(fresh);
      await refresh();
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Löschen fehlgeschlagen.');
    }
  };

  return (
    <div className="px-4 pt-3">
      <button type="button" onClick={openNew} className="btn-primary w-full mb-3">
        <Plus size={18} className="inline mr-1" /> Neue Kategorie
      </button>
      <ul className="space-y-2">
        {categories.length === 0 && (
          <li className="card p-6 text-center text-ink-500">Noch keine Kategorien.</li>
        )}
        {categories.map((c) => (
          <li key={c.id} className="card flex items-center gap-3 p-3">
            <span
              aria-hidden
              className="h-10 w-1.5 rounded-full"
              style={{ backgroundColor: c.color }}
            />
            <div className="min-w-0 flex-1">
              <p className="font-semibold truncate">{c.name}</p>
              <p className="text-xs text-ink-500">{counts.get(c.id) ?? 0} Produkte</p>
            </div>
            <button
              type="button"
              onClick={() => openEdit(c)}
              className="tap rounded-full hover:bg-gray-100"
              aria-label="Bearbeiten"
            >
              <Pencil size={18} className="text-ink-700" />
            </button>
            <button
              type="button"
              onClick={() => onDelete(c)}
              className="tap rounded-full hover:bg-red-50"
              aria-label="Löschen"
            >
              <Trash2 size={18} className="text-red-600" />
            </button>
          </li>
        ))}
      </ul>

      <BottomSheet
        open={editor !== null}
        onClose={() => setEditor(null)}
        title={editor === 'new' ? 'Neue Kategorie' : 'Kategorie bearbeiten'}
      >
        <div className="space-y-3">
          <div>
            <label className="label" htmlFor="cat-name">Name *</label>
            <input
              id="cat-name"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="z.B. Getränke"
            />
          </div>
          <div>
            <label className="label">Farbe</label>
            <div className="flex flex-wrap gap-2">
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`h-9 w-9 rounded-full border-2 ${color === c ? 'border-ink-900' : 'border-transparent'}`}
                  style={{ backgroundColor: c }}
                  aria-label={`Farbe ${c}`}
                />
              ))}
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="h-9 w-9 rounded-full border border-gray-200 bg-white"
                aria-label="Eigene Farbe"
              />
            </div>
          </div>
          <div>
            <label className="label" htmlFor="cat-order">Sortierung</label>
            <input
              id="cat-order"
              className="input"
              type="number"
              min={0}
              value={sortOrder}
              onChange={(e) => setSortOrder(e.target.value)}
            />
          </div>
          <button
            type="button"
            disabled={!name.trim() || submitting}
            onClick={submit}
            className="btn-primary w-full disabled:opacity-50"
          >
            {submitting ? 'Speichern …' : 'Speichern'}
          </button>
        </div>
      </BottomSheet>
    </div>
  );
}