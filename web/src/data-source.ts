// Fetches the exported data files (hosted / PWA build).
export async function getFile(name: string): Promise<any> {
  const root = document.body.dataset.mode === "console" ? "../" : "./";
  const r = await fetch(new URL(`${root}data/${name}`, location.href).toString());
  if (!r.ok) throw new Error(`Failed to load ${name}`);
  return r.json();
}
export const INLINE = false;
