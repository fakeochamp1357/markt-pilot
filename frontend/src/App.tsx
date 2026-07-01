import { Route, Routes } from 'react-router-dom';
import { AppShell } from '@/layouts/AppShell';
import { PreislistePage } from '@/pages/PreislistePage';
import { InventoryPage } from '@/pages/InventoryPage';
import { CategoriesPage } from '@/pages/CategoriesPage';
import { ScannerPage } from '@/pages/ScannerPage';
import { MorePage } from '@/pages/MorePage';
import { POSPage } from '@/pages/POSPage';
import { ReceiptsPage } from '@/pages/ReceiptsPage';
import { useOutboxSync } from '@/hooks/useOutboxSync';
import { useTheme } from '@/hooks/useTheme';

export default function App() {
  // Theme muss VOR dem ersten Render wirken (sonst blitzt das helle
  // Schema kurz auf). useOutboxSync mounted den Health-Hook.
  useTheme();
  useOutboxSync();
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<PreislistePage />} />
        <Route path="/pos" element={<POSPage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/scanner" element={<ScannerPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="/receipts" element={<ReceiptsPage />} />
        <Route path="*" element={<POSPage />} />
      </Route>
    </Routes>
  );
}