import { useState } from "react";
import type { Route } from "./+types/home";
import products from "../products.json";

type Product = { id: number; name: string; price: number; category: string };

export function meta(_: Route.MetaArgs) {
  return [{ title: "Widget Showcase — Remix" }];
}

// Loader provides the 24 products (server-side), fresh on every request.
export function loader() {
  return { products: products as Product[], renderedAt: Date.now() };
}

function ThemeToggle() {
  const [dark, setDark] = useState(false);

  function toggle() {
    const next = !dark;
    setDark(next);
    const theme = next ? "dark" : "light";
    document.documentElement.className = theme;
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* ignore */
    }
  }

  return (
    <button type="button" onClick={toggle} aria-label="Toggle theme">
      {dark ? "Light" : "Dark"} mode
    </button>
  );
}

function Counter() {
  const [count, setCount] = useState(0);
  return (
    <div className="counter">
      <button type="button" onClick={() => setCount((c) => c + 1)}>
        Count: {count}
      </button>
    </div>
  );
}

export default function Home({ loaderData }: Route.ComponentProps) {
  const { products, renderedAt } = loaderData;
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();

  return (
    <div className="wrap">
      <header>
        <span className="brand">Remix</span>
        <ThemeToggle />
      </header>

      <section className="hero">
        <h1>Widget Showcase</h1>
        <p>A fair, head-to-head benchmark app rendered server-side.</p>
      </section>

      <Counter />

      <input
        className="search"
        type="text"
        placeholder="Filter products…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Filter products"
      />

      <div className="grid">
        {products.map((p) => {
          const hidden = q !== "" && !p.name.toLowerCase().includes(q);
          return (
            <div className="card" key={p.id} hidden={hidden}>
              <div className="name">{p.name}</div>
              <div className="cat">{p.category}</div>
              <div className="price">${p.price}</div>
            </div>
          );
        })}
      </div>

      <footer data-rendered-at={renderedAt}>Built with Remix</footer>
    </div>
  );
}
