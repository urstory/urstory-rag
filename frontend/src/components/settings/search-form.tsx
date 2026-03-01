"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSettings, useUpdateSettings } from "@/lib/queries";
import { toast } from "sonner";
import { Save } from "lucide-react";

const searchSchema = z.object({
  mode: z.enum(["hybrid", "vector", "keyword"]),
  keyword_engine: z.string(),
  rrf_constant: z.number().min(1).max(200),
  vector_weight: z.number().min(0).max(1),
  keyword_weight: z.number().min(0).max(1),
});

type SearchFormData = z.infer<typeof searchSchema>;

export function SearchForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<SearchFormData>({
    resolver: zodResolver(searchSchema),
    values: settings?.search ?? {
      mode: "hybrid",
      keyword_engine: "elasticsearch",
      rrf_constant: 60,
      vector_weight: 0.5,
      keyword_weight: 0.5,
    },
  });

  const onSubmit = async (data: SearchFormData) => {
    try {
      await updateMutation.mutateAsync({ search: data });
      toast.success("검색 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  const vectorWeight = form.watch("vector_weight");
  const keywordWeight = form.watch("keyword_weight");
  const rrfConstant = form.watch("rrf_constant");

  return (
    <Card>
      <CardHeader>
        <CardTitle>검색 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-2">
            <Label>검색 모드</Label>
            <Select
              value={form.watch("mode")}
              onValueChange={(v) => form.setValue("mode", v as SearchFormData["mode"])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="hybrid">하이브리드</SelectItem>
                <SelectItem value="vector">벡터</SelectItem>
                <SelectItem value="keyword">키워드</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>키워드 엔진</Label>
            <Select
              value={form.watch("keyword_engine")}
              onValueChange={(v) => form.setValue("keyword_engine", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="elasticsearch">Elasticsearch (Nori)</SelectItem>
                <SelectItem value="bm25">BM25 (kiwipiepy)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>RRF Constant (k): {rrfConstant}</Label>
            <Input
              type="number"
              value={rrfConstant}
              onChange={(e) => form.setValue("rrf_constant", Number(e.target.value))}
              min={1}
              max={200}
            />
          </div>

          <div className="space-y-2">
            <Label>벡터 가중치: {vectorWeight.toFixed(2)}</Label>
            <Slider
              value={[vectorWeight]}
              onValueChange={(v) => form.setValue("vector_weight", v[0])}
              min={0}
              max={1}
              step={0.05}
            />
          </div>

          <div className="space-y-2">
            <Label>키워드 가중치: {keywordWeight.toFixed(2)}</Label>
            <Slider
              value={[keywordWeight]}
              onValueChange={(v) => form.setValue("keyword_weight", v[0])}
              min={0}
              max={1}
              step={0.05}
            />
          </div>

          <Button type="submit" disabled={updateMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {updateMutation.isPending ? "저장 중..." : "저장"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
