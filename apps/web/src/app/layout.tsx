import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "DST Assistant — Hỏi đáp tiếng Việt có nguồn",
  description: "Trợ lý hỏi đáp tiếng Việt có dẫn nguồn về Don't Starve Together.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
