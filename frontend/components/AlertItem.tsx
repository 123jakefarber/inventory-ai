"use client";

import type { Alert } from "@/types";
import { markAlertRead } from "@/lib/api";
import { useRouter } from "next/navigation";

const typeConfig = {
  stockout: { label: "Stockout", color: "text-red-400", bg: "bg-red-500/10" },
  reorder: { label: "Reorder", color: "text-amber-400", bg: "bg-amber-500/10" },
  dead_inventory: { label: "Dead Stock", color: "text-blue-400", bg: "bg-blue-500/10" },
};

export default function AlertItem({ alert }: { alert: Alert }) {
  const router = useRouter();
  const config = typeConfig[alert.type] || typeConfig.reorder;

  const handleMarkRead = async () => {
    await markAlertRead(alert.id);
    router.refresh();
  };

  return (
    <div
      className={`border border-gray-800 rounded-lg p-4 flex items-start justify-between gap-4 ${
        alert.is_read ? "opacity-50" : ""
      }`}
    >
      <div className="flex items-start gap-3 min-w-0">
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 mt-0.5 ${config.color} ${config.bg}`}>
          {config.label}
        </span>
        <div className="min-w-0">
          <p className="text-sm text-white">{alert.message}</p>
          <p className="text-xs text-gray-500 mt-1">
            {alert.product_name} · {alert.created_at ? new Date(alert.created_at).toLocaleDateString() : ""}
          </p>
        </div>
      </div>

      {!alert.is_read && (
        <button
          onClick={handleMarkRead}
          className="text-xs text-gray-500 hover:text-white shrink-0 px-2 py-1 rounded hover:bg-gray-800 transition-colors"
        >
          Mark read
        </button>
      )}
    </div>
  );
}
