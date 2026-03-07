"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/lib/auth-context";
import { setAuthHelpers } from "@/lib/api";

function ApiAuthSync({ children }: { children: React.ReactNode }) {
  const { accessToken, refreshAccessToken, logout } = useAuth();

  useEffect(() => {
    setAuthHelpers({
      getAccessToken: () => accessToken,
      refreshAccessToken,
      onAuthFailure: () => {
        logout();
        window.location.href = "/login";
      },
    });
  }, [accessToken, refreshAccessToken, logout]);

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ApiAuthSync>
          <TooltipProvider>
            {children}
            <Toaster position="top-right" richColors />
          </TooltipProvider>
        </ApiAuthSync>
      </AuthProvider>
    </QueryClientProvider>
  );
}
