"use client";

import { useEffect, useState } from "react";
import { fetchDashboard, fetchPredictions } from "@/lib/api";
import StatsCard from "@/components/StatsCard";
import ActionCard from "@/components/ActionCard";
import StockoutTable from "@/components/StockoutTable";
import type { DashboardData, StockoutPrediction } from "@/types";

export default function CommandCenter() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [predictions, setPredictions] = useState<StockoutPrediction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [dash, predData] = await Promise.all([fetchDashboard(), fetchPredictions()]);
        setDashboard(dash);
        setPredictions(predData.predictions);
      } catch {}
      setLoading(false);
    }
    load();
  }, []);

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const allActions = [
    ...(dashboard?.critical_alerts ?? []),
    ...(dashboard?.reorder_actions ?? []),
  ];

  const criticalPredictions = predictions.filter(
    (p) => p.days_until_stockout !== null && p.days_until_stockout <= 30
  );

  const deadStock = predictions.filter(
    (p) => p.days_until_stockout !== null && p.days_until_stockout > 90
  );

  return (
    <div className="max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Command Center</h1>
        <p className="text-gray-500 text-sm mt-1">{today}</p>
      </div>

      {loading ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">Loading dashboard...</p>
        </div>
      ) : !dashboard ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">Connecting to backend...</p>
          <p className="text-gray-600 text-sm mt-2">
            Start the API server: cd backend &amp;&amp; uvicorn main:app --reload
          </p>
        </div>
      ) : (
        <>
          {/* Stats Row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatsCard
              label="Total SKUs"
              value={dashboard.inventory_summary.total_variants}
              color="white"
            />
            <StatsCard
              label="Critical Alerts"
              value={dashboard.prediction_summary.critical}
              color="red"
            />
            <StatsCard
              label="Items to Reorder"
              value={dashboard.prediction_summary.warning + dashboard.prediction_summary.critical}
              color="amber"
            />
            <StatsCard
              label="Units in Stock"
              value={dashboard.inventory_summary.total_units_in_stock.toLocaleString()}
              color="green"
            />
          </div>

          {/* Today's Actions */}
          {allActions.length > 0 && (
            <section className="mb-8">
              <h2 className="text-lg font-semibold mb-4">Today&apos;s Actions</h2>
              <div className="space-y-3">
                {allActions.slice(0, 5).map((a) => (
                  <ActionCard key={a.id} alert={a} />
                ))}
              </div>
            </section>
          )}

          {/* Stockout Warnings */}
          <section className="mb-8">
            <h2 className="text-lg font-semibold mb-4">Stockout Warnings</h2>
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <StockoutTable predictions={criticalPredictions} />
            </div>
          </section>

          {/* Dead Inventory */}
          {deadStock.length > 0 && (
            <section>
              <h2 className="text-lg font-semibold mb-4">Dead Inventory</h2>
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <StockoutTable predictions={deadStock} />
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
