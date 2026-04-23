"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { SearchForm } from "@/components/settings/search-form";

export default function SearchSettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings" aria-label="설정 목록으로 돌아가기">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">검색 설정</h2>
      </div>
      <SearchForm />
    </div>
  );
}
