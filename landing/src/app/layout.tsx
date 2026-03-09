import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AnimeCaos",
  description: "Redirecting...",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt">
      <body>{children}</body>
    </html>
  );
}
