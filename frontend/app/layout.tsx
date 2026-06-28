import type { Metadata } from "next";
import "./globals.css";
import { SelectionProvider } from "@/lib/selection";

export const metadata: Metadata = {
  title: "Project Atlas",
  description: "Graph-based intelligence & knowledge platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* SelectionProvider lives at the root so brushed/selected entities stay
          linked as the analyst moves between graph, table, map, and timeline. */}
      <body>
        <SelectionProvider>{children}</SelectionProvider>
      </body>
    </html>
  );
}
