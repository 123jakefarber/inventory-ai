"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { getSquareAuthUrl, disconnectSquare, seedDemoData, squareSync } from "@/lib/api";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const searchParams = useSearchParams();
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState("");

  // Check for Square OAuth callback result
  useEffect(() => {
    const square = searchParams.get("square");
    if (square === "connected") {
      setStatus("Square connected successfully!");
      refreshUser();
    } else if (square === "error") {
      setStatus("Failed to connect Square. Please try again.");
    }
  }, [searchParams, refreshUser]);

  const handleConnectSquare = async () => {
    setLoading("connect");
    try {
      const data = await getSquareAuthUrl();
      window.location.href = data.url;
    } catch (err: any) {
      setStatus(err.message || "Failed to start Square connection");
      setLoading("");
    }
  };

  const handleDisconnectSquare = async () => {
    setLoading("disconnect");
    try {
      await disconnectSquare();
      await refreshUser();
      setStatus("Square disconnected.");
    } catch (err: any) {
      setStatus(err.message || "Failed to disconnect Square");
    }
    setLoading("");
  };

  const handleSeedDemo = async () => {
    setLoading("demo");
    try {
      await seedDemoData();
      setStatus("Demo data loaded! Check the dashboard.");
    } catch (err: any) {
      setStatus(err.message || "Failed to load demo data");
    }
    setLoading("");
  };

  const handleSync = async () => {
    setLoading("sync");
    try {
      const result = await squareSync();
      if (result.status === "not_connected") {
        setStatus("Connect your Square account first.");
      } else {
        setStatus("Sync complete!");
      }
    } catch (err: any) {
      setStatus(err.message || "Sync failed");
    }
    setLoading("");
  };

  return (
    <div className="max-w-2xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">Manage your account and integrations</p>
      </div>

      {status && (
        <div className="mb-6 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm text-gray-300">
          {status}
        </div>
      )}

      {/* Account */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Account</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-3">
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-400">Email</span>
            <span className="text-sm text-white">{user?.email}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-sm text-gray-400">Business</span>
            <span className="text-sm text-white">{user?.business_name || "Not set"}</span>
          </div>
        </div>
      </section>

      {/* Square Integration */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Square Integration</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm font-medium text-white">Square POS</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {user?.square_connected
                  ? "Connected — syncing inventory and sales data"
                  : "Connect your Square account to sync real inventory data"}
              </p>
            </div>
            {user?.square_connected ? (
              <div className="flex gap-2">
                <button
                  onClick={handleSync}
                  disabled={loading === "sync"}
                  className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded-lg transition-colors"
                >
                  {loading === "sync" ? "Syncing..." : "Sync Now"}
                </button>
                <button
                  onClick={handleDisconnectSquare}
                  disabled={loading === "disconnect"}
                  className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 disabled:bg-gray-700 text-red-400 rounded-lg transition-colors"
                >
                  {loading === "disconnect" ? "..." : "Disconnect"}
                </button>
              </div>
            ) : (
              <button
                onClick={handleConnectSquare}
                disabled={loading === "connect"}
                className="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white font-medium rounded-lg transition-colors"
              >
                {loading === "connect" ? "Connecting..." : "Connect Square"}
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Demo Data */}
      <section className="mb-8">
        <h2 className="text-lg font-semibold mb-4">Demo Data</h2>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm font-medium text-white">Load Demo Products</p>
              <p className="text-xs text-gray-500 mt-0.5">
                Populate your account with sample apparel data for testing
              </p>
            </div>
            <button
              onClick={handleSeedDemo}
              disabled={loading === "demo"}
              className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 disabled:bg-gray-700 text-white rounded-lg transition-colors"
            >
              {loading === "demo" ? "Loading..." : "Load Demo Data"}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
