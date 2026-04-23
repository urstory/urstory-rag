"use client";

import { useState } from "react";
import { Sidebar } from "./sidebar";
import { Header } from "./header";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Skip-link for keyboard / screen reader users */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        본문으로 건너뛰기
      </a>

      {/* Desktop sidebar */}
      <aside
        data-testid="sidebar"
        aria-label="사이드바"
        className="hidden w-60 shrink-0 border-r md:block"
      >
        <ScrollArea className="h-full">
          <Sidebar />
        </ScrollArea>
      </aside>

      {/* Mobile sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" className="w-60 p-0" aria-label="모바일 메뉴">
          <ScrollArea className="h-full">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
          </ScrollArea>
        </SheetContent>
      </Sheet>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuToggle={() => setMobileOpen(true)} />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-auto p-4 md:p-6 focus:outline-none"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
