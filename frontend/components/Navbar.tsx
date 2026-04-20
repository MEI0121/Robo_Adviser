"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/assess", label: "Risk Assessment" },
  { href: "/profile", label: "My Profile" },
  { href: "/frontier", label: "Efficient Frontier" },
  { href: "/portfolio", label: "Portfolio" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-slate-700/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white font-bold text-sm">
              RA
            </div>
            <span className="font-bold text-white text-lg hidden sm:block">
              Robo<span className="text-blue-400">Adviser</span>
            </span>
          </Link>

          {/* Navigation links */}
          <div className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`px-3 py-2 rounded-md text-sm font-medium transition-colors duration-150 ${
                    active
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:text-white hover:bg-slate-700"
                  }`}
                >
                  <span className="hidden md:inline">{item.label}</span>
                  <span className="md:hidden">{item.label.split(" ")[0]}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
