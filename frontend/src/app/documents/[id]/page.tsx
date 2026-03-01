"use client";

import { use } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ChunkViewer } from "@/components/documents/chunk-viewer";
import { IndexingStatus } from "@/components/documents/indexing-status";
import { useDocument, useDocumentChunks, useReindexDocument } from "@/lib/queries";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { toast } from "sonner";

export default function DocumentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data: doc, isLoading: docLoading } = useDocument(id);
  const { data: chunks, isLoading: chunksLoading } = useDocumentChunks(id);
  const reindexMutation = useReindexDocument();

  const handleReindex = async () => {
    try {
      await reindexMutation.mutateAsync(id);
      toast.success("재인덱싱이 시작되었습니다.");
    } catch {
      toast.error("재인덱싱에 실패했습니다.");
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  if (docLoading) {
    return <p className="text-muted-foreground">로딩 중...</p>;
  }

  if (!doc) {
    return <p className="text-muted-foreground">문서를 찾을 수 없습니다.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/documents">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">문서 상세</h2>
      </div>

      {/* Metadata */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{doc.filename}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={handleReindex}
              disabled={reindexMutation.isPending}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              재인덱싱
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <div>
              <p className="text-muted-foreground">파일 타입</p>
              <Badge variant="outline">{doc.file_type}</Badge>
            </div>
            <div>
              <p className="text-muted-foreground">파일 크기</p>
              <p className="font-medium">{formatSize(doc.file_size)}</p>
            </div>
            <div>
              <p className="text-muted-foreground">상태</p>
              <IndexingStatus status={doc.status} />
            </div>
            <div>
              <p className="text-muted-foreground">청크 수</p>
              <p className="font-medium">{doc.chunk_count}</p>
            </div>
            <div>
              <p className="text-muted-foreground">소스</p>
              <Badge variant={doc.source === "upload" ? "secondary" : "outline"}>
                {doc.source === "upload" ? "업로드" : "감시"}
              </Badge>
            </div>
            <div>
              <p className="text-muted-foreground">생성일</p>
              <p className="font-medium">
                {new Date(doc.created_at).toLocaleDateString("ko-KR")}
              </p>
            </div>
            <div>
              <p className="text-muted-foreground">수정일</p>
              <p className="font-medium">
                {new Date(doc.updated_at).toLocaleDateString("ko-KR")}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Separator />

      {/* Chunks */}
      <ChunkViewer chunks={chunks ?? []} isLoading={chunksLoading} />
    </div>
  );
}
