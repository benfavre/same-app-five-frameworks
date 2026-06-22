"use resumable";
/** @jsxImportSource @bext-stack/framework/signals */
import { signal } from "@bext-stack/framework/signals";

// Resumable counter: the component runs ONCE on the server. The client
// reconstructs `count` from the serialized value and resolves the click handler
// from the lifted factory map — it never re-runs this function.
export default function Counter(props: { start?: number }) {
  const count = signal(props.start ?? 0);
  return (
    <button class="btn" onClick={() => count.value++}>
      Count: {count.value}
    </button>
  );
}
