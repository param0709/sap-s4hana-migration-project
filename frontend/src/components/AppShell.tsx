import { Link, NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

const ROUTE_LABELS: Record<string, string> = {
  "/": "Projects",
  "/projects/new": "Projects / New",
};

function routeLabel(pathname: string): string {
  if (ROUTE_LABELS[pathname]) return ROUTE_LABELS[pathname];
  if (pathname.includes("/upload")) return "Projects / Upload";
  return "Projects";
}

export function AppShell({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();

  return (
    <>
      <header className="masthead">
        <div className="masthead__inner">
          <Link to="/" className="masthead__mark" style={{ color: "var(--ink)" }}>
            Migration Co-Pilot
          </Link>
          <span className="masthead__route">{routeLabel(pathname)}</span>
          <nav className="masthead__nav">
            <NavLink to="/">Projects</NavLink>
            <NavLink to="/projects/new">New project</NavLink>
          </nav>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
  );
}
