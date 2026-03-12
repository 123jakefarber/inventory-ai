"use client";

import { useEffect, useState } from "react";
import { fetchPredictions, refreshPredictions } from "@/lib/api";
import StockoutTable from "@/components/StockoutTable";
import type { StockoutPrediction } from "@/types";

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState<StockoutPrediction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async () => {
    try {
      const data = await fetchPredictions();
      setPredictions(data.predictions);
    } catch {
      /* backend not running */
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await refreshPredictions();
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div className="max-w-6xl">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Predictions</h1>
          <p className="text-gray-500 text-sm mt-1">
            AI stockout predictions for all variants
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {refreshing ? "Refreshing..." : "Refresh Predictions"}
        </button>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        {loading ? (
          <p className="text-gray-500 text-sm py-4">Loading predictions...</p>
        ) : (
          <StockoutTable predictions={predictions} />
        )}
      </div>
    </div>
  );
}
