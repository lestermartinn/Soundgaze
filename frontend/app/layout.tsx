import type { Metadata } from "next";
import { Syne } from "next/font/google";
import Providers from "./providers";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "Soundgaze — Music Universe Explorer",
  description: "Navigate a 3D universe of songs. Explore, discover, and save music.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={syne.variable}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
