/** @jsxImportSource @bext-stack/framework */

// Minimal, chrome-free Document for the head-to-head benchmark. No marketing
// nav, no fonts, no analytics — just the app, so the measured client JS / TTFB
// reflect the framework floor, not site chrome. Inline CSS only.
const THEME_INIT =
  "try{if(localStorage.getItem('theme')==='dark')document.documentElement.classList.add('dark')}catch(e){}";

const CSS = `
*,*::before,*::after{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;line-height:1.5;background:#fff;color:#111}
html.dark body{background:#0c0f14;color:#e7e9ee}
.wrap{max-width:880px;margin:0 auto;padding:1.5rem 1.25rem 3rem}
.hd{display:flex;align-items:center;justify-content:space-between;padding-bottom:1rem;border-bottom:1px solid #eee}
html.dark .hd{border-color:#222}
.brand{font-weight:700;font-size:1.1rem}
.hero{padding:2rem 0 1rem}
.hero h1{font-size:2rem;margin:0 0 .4rem}
.hero p{margin:0;color:#555;max-width:48ch}
html.dark .hero p{color:#9aa3b2}
.block{padding:.5rem 0 1.5rem}
.btn{padding:.55rem 1.2rem;font-size:1rem;border:1px solid #0a7;border-radius:9px;background:#fff;color:#063;cursor:pointer;font-family:inherit}
.btn:hover{background:#f2fbf7}
.btn.ghost{border-color:#ccc;color:inherit;background:transparent}
html.dark .btn{background:#11161f;color:#5fe3b0;border-color:#1d5}
.catalog{padding-top:.5rem}
.search{width:100%;padding:.6rem .8rem;font-size:1rem;border:1px solid #ddd;border-radius:9px;margin-bottom:1rem;font-family:inherit;background:#fff;color:#111}
html.dark .search{background:#11161f;color:#e7e9ee;border-color:#243}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.75rem}
.card{border:1px solid #ececec;border-radius:11px;padding:.8rem .9rem;background:#fafafa}
html.dark .card{background:#11161f;border-color:#1b2330}
.card h3{margin:0 0 .5rem;font-size:.98rem}
.meta{display:flex;align-items:center;justify-content:space-between}
.cat{font-size:.78rem;color:#777;background:#fff;border:1px solid #eee;border-radius:6px;padding:.1rem .45rem}
html.dark .cat{background:#0c0f14;border-color:#243;color:#9aa3b2}
.price{font-weight:700}
.ft{margin-top:2.5rem;padding-top:1rem;border-top:1px solid #eee;color:#888;font-size:.9rem}
html.dark .ft{border-color:#222}
`;

export default function Layout(props: { children?: any }): any {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Widget Showcase — bext (PRISM)</title>
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body>{props.children}</body>
    </html>
  );
}
