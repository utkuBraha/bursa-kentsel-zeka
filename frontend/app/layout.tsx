import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import "./geography.css";
import "./civic-blue.css";
export const metadata: Metadata = {
  title: "Bursa · Kentsel Zekâ",
  description:
    "Bursa kentsel hizmet erişilebilirliği ve karar destek platformu",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
