"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [cliente] = useState(() => new QueryClient());
  return <QueryClientProvider client={cliente}>{children}</QueryClientProvider>;
}
