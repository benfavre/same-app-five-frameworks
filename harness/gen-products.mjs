// Deterministic 24-product catalog (no Math.random — banned in some runtimes anyway).
const cats = ["Audio","Wearables","Home","Mobile","Gaming","Office"];
const adjs = ["Nimbus","Vertex","Aero","Lumen","Pulse","Quill","Strata","Onyx"];
const nouns = ["Speaker","Watch","Lamp","Phone","Pad","Mouse","Hub","Cam","Dock","Buds","Key","Mat"];
const products = [];
for (let i = 0; i < 24; i++) {
  const name = `${adjs[i % adjs.length]} ${nouns[i % nouns.length]} ${i + 1}`;
  const price = 19 + ((i * 37) % 480); // deterministic spread 19..498
  const category = cats[i % cats.length];
  products.push({ id: i + 1, name, price, category });
}
process.stdout.write(JSON.stringify(products, null, 2) + "\n");
