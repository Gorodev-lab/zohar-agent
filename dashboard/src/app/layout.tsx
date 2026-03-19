import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ZOHAR // STRATEGIC_MONITOR_2026",
  description: "Centro de Operaciones ZOHAR - Monitor Estratégico de la Gaceta Ecológica Nacional 2026 - SEMARNAT",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
