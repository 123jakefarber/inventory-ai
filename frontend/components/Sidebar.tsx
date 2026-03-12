"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const nav = [
  { href: "/", label: "Command Center", icon: "⌘" },
  { href: "/inventory", label: "Inventory", icon: "📦" },
  { href: "/predictions", label: "Predictions", icon: "📊" },
  { href: "/alerts", label: "Alerts", icon: "🔔" },
  { href: "/settings", label: "Settings", icon: "⚙️" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-gray-950 border-r border-gray-800 flex flex-col z-10">
      <div className="p-5 border-b border-gray-800">
        <h1 className="text-lg font-bold text-white tracking-tight">
          Inventory AI
        </h1>
        <p className="text-xs text-gray-500 mt-0.5">
          {user?.business_name || "Command Center"}
        </p>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {nav.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-900"
              }`}
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-gray-800 space-y-2">
        <div>
          <p className="text-xs text-gray-500 truncate">{user?.email}</p>
          <p className="text-xs mt-0.5">
            {user?.square_connected ? (
              <span className="text-green-400">Square Connected</span>
            ) : (
              <span className="text-amber-500">Square Not Connected</span>
            )}
          </p>
        </div>
        <button
          onClick={logout}
          className="text-xs text-gray-500 hover:text-white transition-colors"
        >
          Sign Out
        </button>
      </div>
    </aside>
  );
}
