"use client";

import { usePathname } from "next/navigation";
import { AuthProvider } from "@/lib/auth";
import AuthGuard from "@/components/AuthGuard";
import Sidebar from "@/components/Sidebar";

const PUBLIC_PATHS = ["/login", "/register"];

export default function ClientLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  return (
    <AuthProvider>
      <AuthGuard>
        {isPublic ? (
          children
        ) : (
          <>
            <Sidebar />
            <main className="ml-56 min-h-screen p-8">{children}</main>
          </>
        )}
      </AuthGuard>
    </AuthProvider>
  );
}
