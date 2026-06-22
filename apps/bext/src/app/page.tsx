/** @jsxImportSource @bext-stack/framework */
import { Raw } from "@bext-stack/framework/jsx-runtime";
import { resumableIsland } from "@bext-stack/framework/signals";
import Counter from "../components/Counter";
import ThemeToggle from "../components/ThemeToggle";
import SearchFilter from "../components/SearchFilter";
import { products } from "../lib/products";

// The "Widget Showcase" canonical app (see bench-h2h/SPEC.md), bext edition.
// Static content is server-rendered; the three interactive units are resumable
// islands — they ship only their lifted handlers/reads + a shared runtime cached
// once, and the components never re-run on the client.

// FAIR-BENCHMARK MODE: force-dynamic = NO ISR cache. The Rust core does a full
// V8 render on every request, exactly like the Node frameworks' per-request SSR.
// The data-rendered-at timestamp below proves it (it differs on every request).
export const dynamic = "force-dynamic";

export async function loader(): Promise<{ renderedAt: number }> {
  return { renderedAt: Date.now() };
}

export default function Page(props: { data?: { renderedAt?: number } }): any {
  const renderedAt = props.data?.renderedAt ?? 0;
  return (
    <main class="wrap">
      <header class="hd">
        <strong class="brand">bext (PRISM)</strong>
        <Raw html={resumableIsland("ThemeToggle", ThemeToggle, {})} />
      </header>

      <section class="hero">
        <h1>Widget Showcase</h1>
        <p>One app, five frameworks. This one resumes: the components run once on the server and never re-run in the browser.</p>
      </section>

      <section class="block">
        <Raw html={resumableIsland("Counter", Counter, { start: 0 })} />
      </section>

      <section class="catalog">
        <Raw html={resumableIsland("SearchFilter", SearchFilter, {})} />
        <div class="grid">
          {products.map((p) => (
            <article class="card" data-name={p.name.toLowerCase()}>
              <h3>{p.name}</h3>
              <div class="meta">
                <span class="cat">{p.category}</span>
                <span class="price">${p.price}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      <footer class="ft" data-rendered-at={renderedAt}>Built with bext (PRISM)</footer>
    </main>
  );
}
