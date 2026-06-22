"use resumable";
/** @jsxImportSource @bext-stack/framework/signals */
import { signal } from "@bext-stack/framework/signals";

// Resumable theme toggle. The reactive label resumes from the serialized value;
// the click handler lifts verbatim and runs on the client without re-running the
// component. Initial theme is applied pre-paint by a tiny script in the layout
// head (standard FOUC-prevention — every framework's app does the same).
export default function ThemeToggle() {
  const dark = signal(false);
  return (
    <button
      class="btn ghost"
      onClick={() => {
        const isDark = document.documentElement.classList.toggle("dark");
        try {
          localStorage.setItem("theme", isDark ? "dark" : "light");
        } catch (e) {}
        dark.value = isDark;
      }}
    >
      {dark.value ? "Light mode" : "Dark mode"}
    </button>
  );
}
