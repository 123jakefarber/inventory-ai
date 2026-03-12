"use client";

import { useAuth } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";

const PUBLIC_PATHS = ["/login", "/register"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const isPublic = PUBLIC_PATHS.includes(pathname);

  useEffect(() => {
    if (loading) return;

    if (!user && !isPublic) {
      router.replace("/login");
    }

    if (user && isPublic) {
      router.replace("/");
    }
  }, [user, loading, isPublic, router]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  // Public pages (login/register) — show without sidebar
  if (isPublic) {
    return <>{children}</>;
  }

  // Not logged in — wait for redirect
  if (!user) {
    return null;
  }

  return <>{children}</>;
}
