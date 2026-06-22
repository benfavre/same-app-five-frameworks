"use client";

import { useState } from "react";

type Product = {
  id: number;
  name: string;
  price: number;
  category: string;
};

export default function Catalog({ products }: { products: Product[] }) {
  const [query, setQuery] = useState("");
  const q = query.toLowerCase();

  return (
    <>
      <input
        className="search"
        type="text"
        placeholder="Filter products…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="grid">
        {products.map((p) => {
          const hidden = q !== "" && !p.name.toLowerCase().includes(q);
          return (
            <div className="card" key={p.id} hidden={hidden}>
              <div className="name">{p.name}</div>
              <div className="category">{p.category}</div>
              <div className="price">${p.price}</div>
            </div>
          );
        })}
      </div>
    </>
  );
}
