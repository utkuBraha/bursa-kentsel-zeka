import { copyFile, mkdir } from "node:fs/promises";

const target = new URL("../public/maplibre/", import.meta.url);
await mkdir(target, { recursive: true });
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  const source = new URL(
    `../node_modules/maplibre-gl/dist/${file}`,
    import.meta.url,
  );
  await copyFile(source, new URL(file, target));
}
