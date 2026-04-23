"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search } from "lucide-react";
import type { SearchRequest } from "@/types";

interface SearchInputProps {
  onSearch: (params: SearchRequest) => void;
  isLoading: boolean;
}

export function SearchInput({ onSearch, isLoading }: SearchInputProps) {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<"hybrid" | "vector" | "keyword" | "cascading">("hybrid");
  const [useHyde, setUseHyde] = useState(true);
  const [useReranking, setUseReranking] = useState(true);
  const [topK, setTopK] = useState(5);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSearch({
      query: query.trim(),
      search_mode: searchMode,
      hyde_enabled: useHyde,
      reranking_enabled: useReranking,
      top_k: topK,
      generate_answer: true,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-4"
      role="search"
      aria-label="RAG 검색"
    >
      <div className="flex gap-2">
        <Label htmlFor="search-query" className="sr-only">
          검색 쿼리
        </Label>
        <Input
          id="search-query"
          placeholder="검색 쿼리를 입력하세요..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading || !query.trim()}>
          <Search className="mr-2 h-4 w-4" aria-hidden="true" />
          {isLoading ? "검색 중..." : "검색"}
        </Button>
      </div>

      {/* Search options */}
      <div
        className="grid gap-4 rounded-md border p-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
        role="group"
        aria-label="검색 옵션"
      >
        <div className="space-y-2">
          <Label htmlFor="search-mode">검색 모드</Label>
          <Select value={searchMode} onValueChange={(v) => setSearchMode(v as typeof searchMode)}>
            <SelectTrigger id="search-mode" aria-label="검색 모드 선택">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="hybrid">하이브리드</SelectItem>
              <SelectItem value="vector">벡터</SelectItem>
              <SelectItem value="keyword">키워드</SelectItem>
              <SelectItem value="cascading">캐스캐이딩</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center justify-between space-y-0 sm:flex-col sm:items-start sm:space-y-2">
          <Label htmlFor="search-hyde">HyDE</Label>
          <Switch
            id="search-hyde"
            checked={useHyde}
            onCheckedChange={setUseHyde}
            aria-label="HyDE 사용"
          />
        </div>

        <div className="flex items-center justify-between space-y-0 sm:flex-col sm:items-start sm:space-y-2">
          <Label htmlFor="search-reranking">리랭킹</Label>
          <Switch
            id="search-reranking"
            checked={useReranking}
            onCheckedChange={setUseReranking}
            aria-label="리랭킹 사용"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="search-topk">Top-K: {topK}</Label>
          <Slider
            id="search-topk"
            value={[topK]}
            onValueChange={(v) => setTopK(v[0])}
            min={1}
            max={20}
            step={1}
            aria-label={`Top-K (현재 ${topK})`}
          />
        </div>
      </div>
    </form>
  );
}
