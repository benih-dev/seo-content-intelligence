import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import { themeScript } from "@/lib/theme";
import { textSizeScript } from "@/lib/text-size";
import "./globals.css";

export const metadata: Metadata = {
  title: "Content Intelligence | Editorial workspace",
  description:
    "An evidence-led workflow from keyword to publication-ready article.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <script dangerouslySetInnerHTML={{ __html: textSizeScript }} />
      </head>
      <body>
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
