import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { routes } from '../routes';

type Props = {
  open: boolean;
  onToggle: () => void;
};

export function SidePanel({ open, onToggle }: Props) {
  return (
    <aside className={`panel ${open ? '' : 'panel--rail'}`} aria-label="Primary">
      <div className="panel__head">
        <button
          type="button"
          className="icon-button"
          onClick={onToggle}
          aria-expanded={open}
          aria-label={open ? 'Collapse navigation' : 'Expand navigation'}
        >
          {open ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>
      </div>
      <nav className="panel__nav">
        {routes.map(({ path, label, icon: Icon }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              `panel__item${isActive ? ' panel__item--active' : ''}`
            }
            title={label}
          >
            <Icon size={18} className="panel__icon" aria-hidden />
            <span className="panel__label">{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
