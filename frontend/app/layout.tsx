import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "School ERP Phase 1",
  description: "Production-ready SaaS foundation starter for school ERP",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
