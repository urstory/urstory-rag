"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, Plus, Trash2, Copy, Check, Key } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/lib/auth-context";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";

export default function ApiKeysPage() {
  const { user } = useAuth();
  const { data: keys, isLoading } = useApiKeys();
  const createKey = useCreateApiKey();
  const revokeKey = useRevokeApiKey();

  const [showCreate, setShowCreate] = useState(false);
  const [showResult, setShowResult] = useState(false);
  const [createdKey, setCreatedKey] = useState("");
  const [copied, setCopied] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [expiresInDays, setExpiresInDays] = useState<string>("");

  if (user?.role !== "admin") {
    return (
      <div className="p-8 text-center text-muted-foreground">
        관리자 권한이 필요합니다.
      </div>
    );
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const result = await createKey.mutateAsync({
        name,
        expires_in_days: expiresInDays ? parseInt(expiresInDays) : null,
      });
      setCreatedKey(result.key);
      setCopied(false);
      setShowCreate(false);
      setShowResult(true);
      setName("");
      setExpiresInDays("");
      toast.success("API Key가 발급되었습니다.");
    } catch {
      toast.error("API Key 발급에 실패했습니다.");
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(createdKey);
    setCopied(true);
    toast.success("클립보드에 복사되었습니다.");
  };

  const handleRevoke = async () => {
    if (!deleteTarget) return;
    try {
      await revokeKey.mutateAsync(deleteTarget);
      setDeleteTarget(null);
      toast.success("API Key가 폐기되었습니다.");
    } catch {
      toast.error("API Key 폐기에 실패했습니다.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings" aria-label="설정 목록으로 돌아가기">
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">API Key 관리</h1>
          <p className="text-muted-foreground text-sm">
            외부 서비스에서 OpenAI 호환 API로 RAG를 사용하기 위한 키를 관리합니다.
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4 mr-2" />
          새 API Key
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            발급된 키 목록
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground text-center py-8">로딩 중...</p>
          ) : !keys || keys.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Key className="h-12 w-12 mx-auto mb-4 opacity-30" />
              <p>발급된 API Key가 없습니다.</p>
              <p className="text-sm mt-1">
                &quot;새 API Key&quot; 버튼을 눌러 키를 발급하세요.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-muted-foreground">
                    <th className="pb-2 font-medium">이름</th>
                    <th className="pb-2 font-medium">키 접두사</th>
                    <th className="pb-2 font-medium">상태</th>
                    <th className="pb-2 font-medium">만료일</th>
                    <th className="pb-2 font-medium">마지막 사용</th>
                    <th className="pb-2 font-medium">생성일</th>
                    <th className="pb-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {keys.map((k) => (
                    <tr key={k.id} className="border-b last:border-0">
                      <td className="py-3 font-medium">{k.name}</td>
                      <td className="py-3">
                        <code className="bg-muted px-2 py-0.5 rounded text-xs">
                          {k.key_prefix}...
                        </code>
                      </td>
                      <td className="py-3">
                        <Badge variant={k.is_active ? "default" : "secondary"}>
                          {k.is_active ? "활성" : "폐기됨"}
                        </Badge>
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {k.expires_at
                          ? new Date(k.expires_at).toLocaleDateString("ko-KR")
                          : "무기한"}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {k.last_used_at
                          ? new Date(k.last_used_at).toLocaleDateString("ko-KR")
                          : "-"}
                      </td>
                      <td className="py-3 text-muted-foreground">
                        {new Date(k.created_at).toLocaleDateString("ko-KR")}
                      </td>
                      <td className="py-3">
                        {k.is_active && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteTarget(k.id)}
                            aria-label={`API Key "${k.name}" 폐기`}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" aria-hidden="true" />
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 사용법 안내 */}
      <Card>
        <CardHeader>
          <CardTitle>사용법</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-muted-foreground">
            발급된 API Key로 OpenAI SDK를 사용하여 RAG 검색을 할 수 있습니다.
          </p>
          <pre className="bg-muted p-4 rounded-lg overflow-x-auto text-xs">
{`from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="rag_sk_xxxxx",  # 발급받은 키
)

response = client.chat.completions.create(
    model="urstory-rag",
    messages=[{"role": "user", "content": "질문 내용"}],
)
print(response.choices[0].message.content)`}
          </pre>
        </CardContent>
      </Card>

      {/* 발급 다이얼로그 */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>새 API Key 발급</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <Label>이름</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="사내 포털 연동, 테스트용 등"
                required
              />
            </div>
            <div>
              <Label>만료 기간 (일)</Label>
              <Input
                type="number"
                value={expiresInDays}
                onChange={(e) => setExpiresInDays(e.target.value)}
                placeholder="비워두면 무기한"
                min={1}
              />
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>
                취소
              </Button>
              <Button type="submit" disabled={createKey.isPending}>
                {createKey.isPending ? "발급 중..." : "발급"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 키 표시 다이얼로그 */}
      <Dialog open={showResult} onOpenChange={(open) => { if (copied) setShowResult(open); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>API Key가 발급되었습니다</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="bg-muted p-3 rounded-lg flex items-center gap-2">
              <code className="flex-1 text-sm break-all">{createdKey}</code>
              <Button
                size="icon"
                variant="ghost"
                onClick={handleCopy}
                aria-label={copied ? "복사 완료" : "API Key 복사"}
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-500" aria-hidden="true" />
                ) : (
                  <Copy className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>
            </div>
            <p className="text-sm text-destructive font-medium">
              이 키는 다시 볼 수 없습니다. 반드시 복사하여 안전하게 보관하세요.
            </p>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowResult(false)} disabled={!copied}>
              {copied ? "확인" : "키를 먼저 복사하세요"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 폐기 확인 다이얼로그 */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>API Key 폐기</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            이 키를 폐기하면 즉시 사용할 수 없게 됩니다. 이 작업은 되돌릴 수 없습니다.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              취소
            </Button>
            <Button variant="destructive" onClick={handleRevoke} disabled={revokeKey.isPending}>
              {revokeKey.isPending ? "폐기 중..." : "폐기"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
