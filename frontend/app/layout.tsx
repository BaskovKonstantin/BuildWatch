import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import "./oc.css";
import "leaflet/dist/leaflet.css";
import { AssistantDock } from "@/components/AssistantDock";
import { PageGuide } from "@/components/PageGuide";

// SF Pro is used natively on Apple devices; Inter is the closest open
// substitute for Windows/Linux and keeps the iOS look consistent.
const inter = Inter({
  subsets: ["latin", "cyrillic"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "BuildWatch — монитор стройконтроля",
  description:
    "Автоматизированный сервис поиска нарушений на строительных площадках Москвы",
};

export const viewport: Viewport = {
  // Editorial identity is print-light; no auto-dark.
  themeColor: "#F6F4EF",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" className={inter.variable}>
      <head>
        {/* Apply the saved visual identity before first paint to avoid a flash. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              'try{var t=localStorage.getItem("buildwatch_theme");'
              + 'if(t==="ios"){localStorage.removeItem("buildwatch_theme")}'
              + 'else if(t){document.documentElement.dataset.theme=t}}catch(e){}',
          }}
        />
      </head>
      <body>{children}<AssistantDock /><PageGuide /></body>
    </html>
  );
}
