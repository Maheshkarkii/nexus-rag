import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Research Assistant | Production Platform",
  description:
    "A modern, production-oriented platform for multi-document deep research, semantic retrieval, and autonomous agentic synthesis.",
  keywords: ["AI", "Research Assistant", "RAG", "FastAPI", "Next.js", "PostgreSQL", "Qdrant", "LangGraph"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased min-h-screen bg-background text-foreground selection:bg-primary/30 selection:text-primary-foreground">
        {children}
      </body>
    </html>
  );
}
