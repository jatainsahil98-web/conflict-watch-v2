// Single-file build: every data file is inlined at build time (works from a USB stick, no server).
const raw = import.meta.glob("../public/data/*", { eager: true, query: "?raw", import: "default" }) as Record<string, string>;
const cache: Record<string, any> = {};
export async function getFile(name: string): Promise<any> {
  if (!cache[name]) cache[name] = JSON.parse(raw[`../public/data/${name}`]);
  return cache[name];
}
export const INLINE = true;
