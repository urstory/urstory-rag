"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { IndexingStatus } from "./indexing-status";
import { useDocuments, useDeleteDocument, useReindexDocument } from "@/lib/queries";
import { Trash2, RefreshCw, ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { toast } from "sonner";
import type { DocumentListParams } from "@/types";

export function DocumentList() {
  const [params, setParams] = useState<DocumentListParams>({
    page: 1,
    size: 20,
    sort: "created_at",
    order: "desc",
    source: "all",
  });
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data, isLoading } = useDocuments(params);
  const deleteMutation = useDeleteDocument();
  const reindexMutation = useReindexDocument();

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteMutation.mutateAsync(deleteId);
      toast.success("문서가 삭제되었습니다.");
      setDeleteId(null);
    } catch {
      toast.error("삭제에 실패했습니다.");
    }
  };

  const handleReindex = async (id: string) => {
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

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3">
        <Select
          value={params.source || "all"}
          onValueChange={(val) =>
            setParams({ ...params, source: val as DocumentListParams["source"], page: 1 })
          }
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">전체</SelectItem>
            <SelectItem value="upload">업로드</SelectItem>
            <SelectItem value="watcher">감시</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={params.order || "desc"}
          onValueChange={(val) =>
            setParams({ ...params, order: val as "asc" | "desc" })
          }
        >
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="desc">최신순</SelectItem>
            <SelectItem value="asc">오래된순</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>파일명</TableHead>
              <TableHead className="hidden sm:table-cell">타입</TableHead>
              <TableHead className="hidden sm:table-cell">크기</TableHead>
              <TableHead>상태</TableHead>
              <TableHead className="hidden md:table-cell">청크</TableHead>
              <TableHead className="hidden md:table-cell">소스</TableHead>
              <TableHead className="hidden lg:table-cell">생성일</TableHead>
              <TableHead className="text-right">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : !data?.items?.length ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
                  문서가 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="max-w-[200px] truncate font-medium">
                    {doc.filename}
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    <Badge variant="outline">{doc.file_type}</Badge>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {formatSize(doc.file_size)}
                  </TableCell>
                  <TableCell>
                    <IndexingStatus status={doc.status} />
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {doc.chunk_count}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    <Badge variant={doc.source === "upload" ? "secondary" : "outline"}>
                      {doc.source === "upload" ? "업로드" : "감시"}
                    </Badge>
                  </TableCell>
                  <TableCell className="hidden lg:table-cell">
                    {new Date(doc.created_at).toLocaleDateString("ko-KR")}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      <Button variant="ghost" size="icon" asChild>
                        <Link href={`/documents/${doc.id}`}>
                          <Eye className="h-4 w-4" />
                        </Link>
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleReindex(doc.id)}
                        disabled={reindexMutation.isPending}
                      >
                        <RefreshCw className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => setDeleteId(doc.id)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            총 {data.total}개 중 {(data.page - 1) * data.size + 1}-
            {Math.min(data.page * data.size, data.total)}
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="icon"
              disabled={data.page <= 1}
              onClick={() => setParams({ ...params, page: (params.page ?? 1) - 1 })}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="text-sm">
              {data.page} / {data.pages}
            </span>
            <Button
              variant="outline"
              size="icon"
              disabled={data.page >= data.pages}
              onClick={() => setParams({ ...params, page: (params.page ?? 1) + 1 })}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteId} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>문서 삭제</DialogTitle>
            <DialogDescription>
              이 문서를 삭제하시겠습니까? 관련된 모든 청크와 인덱스가 함께 삭제됩니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              취소
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "삭제 중..." : "삭제"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
