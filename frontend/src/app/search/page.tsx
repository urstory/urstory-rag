"use client";

import { SearchInput } from "@/components/search/search-input";
import { SearchResults } from "@/components/search/search-results";
import { useSearch } from "@/lib/queries";
import type { SearchRequest } from "@/types";

export default function SearchPage() {
  const searchMutation = useSearch();

  const handleSearch = (params: SearchRequest) => {
    searchMutation.mutate(params);
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">검색 테스트</h2>
      <SearchInput onSearch={handleSearch} isLoading={searchMutation.isPending} />
      {searchMutation.isError && (
        <div className="rounded-md border border-destructive p-4 text-sm text-destructive">
          검색 중 오류가 발생했습니다: {searchMutation.error?.message}
        </div>
      )}
      <SearchResults data={searchMutation.data ?? null} />
    </div>
  );
}
