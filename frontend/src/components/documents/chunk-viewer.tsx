"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Chunk } from "@/types";

interface ChunkViewerProps {
  chunks: Chunk[];
  isLoading: boolean;
}

export function ChunkViewer({ chunks, isLoading }: ChunkViewerProps) {
  if (isLoading) {
    return <p className="text-sm text-muted-foreground">청크 로딩 중...</p>;
  }

  if (!chunks || chunks.length === 0) {
    return <p className="text-sm text-muted-foreground">청크가 없습니다.</p>;
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium">청크 목록</h3>
        <Badge variant="secondary">{chunks.length}개</Badge>
      </div>
      <ScrollArea className="h-[500px]">
        <div className="space-y-3 pr-4">
          {chunks.map((chunk) => (
            <Card key={chunk.id}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center justify-between text-xs">
                  <span>청크 #{chunk.chunk_index + 1}</span>
                  <Badge variant="outline" className="text-xs">
                    {chunk.embedding_status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">
                  {chunk.content}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
