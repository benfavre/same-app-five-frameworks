import products from "./products.json";
import ThemeToggle from "./theme-toggle";
import Counter from "./counter";
import Catalog from "./catalog";

// SSR fresh on every request (no static prerender / no cache) so the
// benchmark renders the page per-request, like the other frameworks.
export const dynamic = "force-dynamic";

export default function Page() {
  return (
    <>
      <header>
        <h2>Next.js</h2>
        <ThemeToggle />
      </header>
      <main className="wrap">
        <section className="hero">
          <h1>Widget Showcase</h1>
          <p>A small catalog of widgets, server-rendered and instantly interactive.</p>
        </section>
        <Counter />
        <Catalog products={products} />
      </main>
      <footer data-rendered-at={Date.now()}>Built with Next.js</footer>
    </>
  );
}
