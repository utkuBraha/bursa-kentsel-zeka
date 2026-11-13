import { NextRequest, NextResponse } from "next/server";
const allowed = new Set([
  "v1/system",
  "v1/dashboard/summary",
  "v1/dashboard/development",
  "v1/accessibility/settings",
  "v1/accessibility/route",
  "v1/accessibility/coverage",
  "v1/accessibility/scenario",
  "v1/accessibility/recommendations",
  "v1/inventory/features",
  "v1/inventory/detail",
  "v1/geography/districts",
  "v1/geography/districts/geojson",
  "v1/geography/neighborhoods",
  "v1/geography/layers",
]);
export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!allowed.has(route))
    return NextResponse.json({ detail: "Kaynak bulunamadı." }, { status: 404 });
  try {
    const origin = process.env.API_INTERNAL_URL || "http://127.0.0.1:8000";
    const response = await fetch(
      `${origin}/api/${route}${request.nextUrl.search}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(
          route === "v1/accessibility/recommendations"
            ? 180000
            : ["v1/accessibility/coverage", "v1/accessibility/scenario"].includes(route)
              ? 90000
              : 8000,
        ),
      },
    );
    return NextResponse.json(await response.json(), {
      status: response.status,
    });
  } catch {
    return NextResponse.json(
      { detail: "Veri altyapısına erişilemiyor. Lütfen yeniden deneyin." },
      { status: 503 },
    );
  }
}
