"use resumable";
/** @jsxImportSource @bext-stack/framework/signals */
import { signal } from "@bext-stack/framework/signals";

// Resumable search filter. The 24 product cards are server-rendered by the page
// (each carries data-name). This island is just the input; its onInput handler
// lifts verbatim and filters the SSR'd cards in place on the client — the
// component never re-runs. (The current resume runtime wires text/attr markers,
// not list re-rendering, so filtering is done imperatively in the handler — which
// is the idiomatic resumable shape: ship the handler, not the framework.)
export default function SearchFilter() {
  const q = signal("");
  return (
    <input
      class="search"
      type="search"
      placeholder="Filter products…"
      onInput={(e: Event) => {
        const v = (e.target as HTMLInputElement).value.toLowerCase();
        q.value = v;
        const cards = document.querySelectorAll("[data-name]");
        for (let i = 0; i < cards.length; i++) {
          const el = cards[i] as HTMLElement;
          el.style.display = (el.getAttribute("data-name") || "").indexOf(v) !== -1 ? "" : "none";
        }
      }}
    />
  );
}
