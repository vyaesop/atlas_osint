import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Project Atlas",
  description: "Graph-based intelligence & knowledge platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
