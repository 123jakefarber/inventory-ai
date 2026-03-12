"use client";

import { useEffect, useState } from "react";
import { fetchInventory } from "@/lib/api";
import InventoryTable from "@/components/InventoryTable";
import type { Product } from "@/types";

export default function InventoryPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchInventory();
        setProducts(data.products);
      } catch {}
      setLoading(false);
    }
    load();
  }, []);

  return (
    <div className="max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Inventory</h1>
        <p className="text-gray-500 text-sm mt-1">All products and current stock levels</p>
      </div>

      {loading ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">Loading inventory...</p>
        </div>
      ) : products.length === 0 ? (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">No inventory data available.</p>
          <p className="text-gray-600 text-sm mt-2">Make sure the backend is running.</p>
        </div>
      ) : (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <InventoryTable products={products} />
        </div>
      )}
    </div>
  );
}
