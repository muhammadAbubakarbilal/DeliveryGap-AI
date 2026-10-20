import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "DeliveryGap AI — Engineering workspace", description: "Evidence-based scope and delivery review." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><a className="skip-link" href="#main-content">Skip to content</a>{children}</body></html>;
}
