import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "BuildWatch — монитор стройконтроля",
  description:
    "Автоматизированный сервис поиска нарушений на строительных площадках Москвы",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
