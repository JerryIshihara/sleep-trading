import { useEffect, useState } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import { SidePanel } from './components/SidePanel';
import { routes } from './routes';

function matchRoute(pathname: string) {
  return routes.find((r) => r.path === pathname) ?? routes[0];
}

export function App() {
  const [panelOpen, setPanelOpen] = useState(true);
  const location = useLocation();
  const active = matchRoute(location.pathname);

  useEffect(() => {
    document.title = `${active.label} · Sleep Trading`;
  }, [active.label]);

  return (
    <div className="app">
      <SidePanel open={panelOpen} onToggle={() => setPanelOpen((v) => !v)} />
      <main className="main">
        <Routes>
          {routes.map(({ path, element }) => (
            <Route key={path} path={path} element={element} />
          ))}
        </Routes>
      </main>
    </div>
  );
}
