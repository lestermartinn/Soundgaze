import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hacklytics 2025",
  description: "Music discovery tool — explore your musical taste in 3D.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
