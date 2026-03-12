"use client";

import { useEffect, useState } from "react";
import { fetchAlerts } from "@/lib/api";
import AlertItem from "@/components/AlertItem";
import type { Alert } from "@/types";

const filters = [
  { label: "All", value: "" },
  { label: "Stockout", value: "stockout" },
  { label: "Reorder", value: "reorder" },
  { label: "Dead Stock", value: "dead_inventory" },
];

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [activeFilter, setActiveFilter] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async (type?: string) => {
    setLoading(true);
    try {
      const data = await fetchAlerts(type || undefined);
      setAlerts(data.alerts);
    } catch {
      /* backend not running */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(activeFilter); }, [activeFilter]);

  return (
    <div className="max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Alerts</h1>
        <p className="text-gray-500 text-sm mt-1">Inventory alerts and recommendations</p>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6">
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setActiveFilter(f.value)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              activeFilter === f.value
                ? "bg-gray-800 text-white"
                : "text-gray-500 hover:text-white hover:bg-gray-900"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500 text-sm">Loading alerts...</p>
      ) : alerts.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">No alerts.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <AlertItem key={a.id} alert={a} />
          ))}
        </div>
      )}
    </div>
  );
}
