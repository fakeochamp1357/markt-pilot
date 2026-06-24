import { Route, Routes } from 'react-router-dom';
import { AppShell } from '@/layouts/AppShell';
import { PreislistePage } from '@/pages/PreislistePage';
import { InventoryPage } from '@/pages/InventoryPage';
import { CategoriesPage } from '@/pages/CategoriesPage';
import { ScannerPage } from '@/pages/ScannerPage';
import { MorePage } from '@/pages/MorePage';
import { useOutboxSync } from '@/hooks/useOutboxSync';

export default function App() {
  useOutboxSync();
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<PreislistePage />} />
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/scanner" element={<ScannerPage />} />
        <Route path="/more" element={<MorePage />} />
        <Route path="*" element={<PreislistePage />} />
      </Route>
    </Routes>
  );
}