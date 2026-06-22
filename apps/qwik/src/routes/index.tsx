import { component$, useSignal } from "@builder.io/qwik";
import { routeLoader$, type DocumentHead } from "@builder.io/qwik-city";
import { products } from "../products";

const FRAMEWORK = "Qwik";

/**
 * Runs on the server for every request (not at build time). Proves the page is
 * rendered fresh per request rather than statically generated.
 */
export const useRenderedAt = routeLoader$(() => Date.now());

/** Header: framework name + theme toggle (flips <html> class, persists to localStorage). */
const ThemeToggle = component$(() => {
  return (
    <button
      type="button"
      aria-label="Toggle theme"
      onClick$={() => {
        const el = document.documentElement;
        const dark = el.classList.toggle("dark");
        try {
          localStorage.setItem("theme", dark ? "dark" : "light");
        } catch {
          /* ignore */
        }
      }}
    >
      Toggle theme
    </button>
  );
});

/** Counter: button labeled "Count: N", click increments. */
const Counter = component$(() => {
  const count = useSignal(0);
  return (
    <button class="accent" type="button" onClick$={() => count.value++}>
      Count: {count.value}
    </button>
  );
});

/** Catalog: search input + 24 SSR'd cards; typing filters visible cards client-side. */
const Catalog = component$(() => {
  const query = useSignal("");
  return (
    <>
      <div class="toolbar">
        <input
          class="search"
          type="search"
          placeholder="Filter products…"
          value={query.value}
          onInput$={(_, el) => (query.value = el.value)}
        />
        <Counter />
      </div>
      <div class="grid">
        {products.map((p) => {
          const q = query.value.trim().toLowerCase();
          const hidden = q !== "" && !p.name.toLowerCase().includes(q);
          return (
            <div class={hidden ? "card hidden" : "card"} key={p.id}>
              <div class="name">{p.name}</div>
              <div class="cat">{p.category}</div>
              <div class="price">${p.price}</div>
            </div>
          );
        })}
      </div>
    </>
  );
});

export default component$(() => {
  const renderedAt = useRenderedAt();
  return (
    <div class="wrap">
      <header class="site">
        <span class="brand">{FRAMEWORK}</span>
        <ThemeToggle />
      </header>

      <section class="hero">
        <h1>Widget Showcase</h1>
        <p>A tiny catalog rendered on the server, resumed in the browser.</p>
      </section>

      <Catalog />

      <footer class="site" data-rendered-at={renderedAt.value}>
        Built with {FRAMEWORK}
      </footer>
    </div>
  );
});

export const head: DocumentHead = {
  title: "Widget Showcase — Qwik",
  meta: [
    {
      name: "description",
      content: "Head-to-head benchmark app built with Qwik.",
    },
  ],
};
