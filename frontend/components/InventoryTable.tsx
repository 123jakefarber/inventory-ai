"use client";

import { useState } from "react";
import type { Product } from "@/types";

function stockColor(stock: number): string {
  if (stock <= 20) return "text-red-400";
  if (stock <= 50) return "text-amber-400";
  return "text-green-400";
}

export default function InventoryTable({ products }: { products: Product[] }) {
  const [search, setSearch] = useState("");

  const filtered = products.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      p.category.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <input
        type="text"
        placeholder="Search products..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full max-w-sm mb-4 px-4 py-2 bg-gray-900 border border-gray-800 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-600"
      />

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-gray-800">
              <th className="pb-3 pr-4">Product</th>
              <th className="pb-3 pr-4">Category</th>
              <th className="pb-3 pr-4">Size</th>
              <th className="pb-3 pr-4">SKU</th>
              <th className="pb-3 pr-4">Stock</th>
              <th className="pb-3">Price</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {filtered.map((product) =>
              product.variants.map((v) => (
                <tr key={v.id} className="hover:bg-gray-900/50">
                  <td className="py-3 pr-4 text-white font-medium">{v.product_name}</td>
                  <td className="py-3 pr-4 text-gray-400">{v.category}</td>
                  <td className="py-3 pr-4 text-gray-400">{v.size}</td>
                  <td className="py-3 pr-4 text-gray-500 font-mono text-xs">{v.sku}</td>
                  <td className={`py-3 pr-4 font-semibold ${stockColor(v.current_stock)}`}>
                    {v.current_stock}
                  </td>
                  <td className="py-3 text-gray-300">${v.price.toFixed(2)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
