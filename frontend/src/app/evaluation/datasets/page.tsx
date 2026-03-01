"use client";

import { useState, useCallback } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ArrowLeft, Plus, FileUp } from "lucide-react";
import { useEvaluationDatasets, useCreateDataset } from "@/lib/queries";
import { toast } from "sonner";

export default function DatasetsPage() {
  const { data, isLoading } = useEvaluationDatasets();
  const createMutation = useCreateDataset();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const handleCreate = useCallback(async () => {
    if (!file || !name.trim()) return;
    const formData = new FormData();
    formData.append("name", name.trim());
    formData.append("description", description.trim());
    formData.append("file", file);
    try {
      await createMutation.mutateAsync(formData);
      toast.success("데이터셋이 생성되었습니다.");
      setOpen(false);
      setName("");
      setDescription("");
      setFile(null);
    } catch {
      toast.error("데이터셋 생성에 실패했습니다.");
    }
  }, [file, name, description, createMutation]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/evaluation">
              <ArrowLeft className="h-4 w-4" />
            </Link>
          </Button>
          <h2 className="text-2xl font-bold">평가 데이터셋</h2>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              데이터셋 생성
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>데이터셋 생성</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>이름</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="데이터셋 이름" />
              </div>
              <div className="space-y-2">
                <Label>설명</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="설명 (선택)" />
              </div>
              <div className="space-y-2">
                <Label>QA 데이터 파일 (JSON)</Label>
                <div className="flex items-center gap-2">
                  <FileUp className="h-4 w-4 text-muted-foreground" />
                  <input
                    type="file"
                    accept=".json"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="text-sm"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {`JSON 형식: [{"question": "...", "ground_truth": "..."}]`}
                </p>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setOpen(false)}>
                  취소
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={!file || !name.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? "생성 중..." : "생성"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>이름</TableHead>
              <TableHead>설명</TableHead>
              <TableHead className="text-right">QA 쌍 수</TableHead>
              <TableHead className="text-right">생성일</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : !data?.items?.length ? (
              <TableRow>
                <TableCell colSpan={4} className="h-24 text-center">
                  데이터셋이 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((ds) => (
                <TableRow key={ds.id}>
                  <TableCell className="font-medium">{ds.name}</TableCell>
                  <TableCell className="text-muted-foreground">{ds.description || "-"}</TableCell>
                  <TableCell className="text-right">{ds.qa_count}</TableCell>
                  <TableCell className="text-right">
                    {new Date(ds.created_at).toLocaleDateString("ko-KR")}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
