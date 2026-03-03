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
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex gap-2">
        <Input
          placeholder="검색 쿼리를 입력하세요..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1"
        />
        <Button type="submit" disabled={isLoading || !query.trim()}>
          <Search className="mr-2 h-4 w-4" />
          {isLoading ? "검색 중..." : "검색"}
        </Button>
      </div>

      {/* Search options */}
      <div className="grid gap-4 rounded-md border p-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-2">
          <Label>검색 모드</Label>
          <Select value={searchMode} onValueChange={(v) => setSearchMode(v as typeof searchMode)}>
            <SelectTrigger>
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
          <Label>HyDE</Label>
          <Switch checked={useHyde} onCheckedChange={setUseHyde} />
        </div>

        <div className="flex items-center justify-between space-y-0 sm:flex-col sm:items-start sm:space-y-2">
          <Label>리랭킹</Label>
          <Switch checked={useReranking} onCheckedChange={setUseReranking} />
        </div>

        <div className="space-y-2">
          <Label>Top-K: {topK}</Label>
          <Slider
            value={[topK]}
            onValueChange={(v) => setTopK(v[0])}
            min={1}
            max={20}
            step={1}
          />
        </div>
      </div>
    </form>
  );
}
