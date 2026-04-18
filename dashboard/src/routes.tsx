import type { ReactNode } from 'react';
import {
  LayoutDashboard,
  Wallet,
  Activity,
  ListOrdered,
  Globe,
  Settings as SettingsIcon,
  type LucideIcon,
} from 'lucide-react';
import { SettingsPage } from './pages/Settings';
import { MarketPage } from './pages/Market';

export type AppRoute = {
  path: string;
  label: string;
  icon: LucideIcon;
  element: ReactNode;
};

export const routes: AppRoute[] = [
  {
    path: '/',
    label: 'Overview',
    icon: LayoutDashboard,
    element: (
      <div className="page">
        <h1>Overview</h1>
      </div>
    ),
  },
  {
    path: '/market',
    label: 'Market',
    icon: Globe,
    element: <MarketPage />,
  },
  {
    path: '/portfolio',
    label: 'Portfolio',
    icon: Wallet,
    element: (
      <div className="page">
        <h1>Portfolio</h1>
      </div>
    ),
  },
  {
    path: '/strategies',
    label: 'Strategies',
    icon: Activity,
    element: (
      <div className="page">
        <h1>Strategies</h1>
      </div>
    ),
  },
  {
    path: '/orders',
    label: 'Orders',
    icon: ListOrdered,
    element: (
      <div className="page">
        <h1>Orders</h1>
      </div>
    ),
  },
  {
    path: '/settings',
    label: 'Settings',
    icon: SettingsIcon,
    element: <SettingsPage />,
  },
];
