"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  useAdminUsers,
  useCreateUser,
  useUpdateUser,
  useDeleteUser,
} from "@/lib/queries";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Plus, Pencil, Trash2, ShieldCheck, ShieldOff } from "lucide-react";
import type { AdminUser } from "@/types";

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const { data, isLoading } = useAdminUsers();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deleteUser = useDeleteUser();

  const [showCreate, setShowCreate] = useState(false);
  const [editTarget, setEditTarget] = useState<AdminUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);

  // Create form
  const [newUsername, setNewUsername] = useState("");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("user");
  const [createError, setCreateError] = useState("");

  // Edit form
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editRole, setEditRole] = useState("");
  const [editActive, setEditActive] = useState(true);
  const [editError, setEditError] = useState("");

  if (currentUser?.role !== "admin") {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-muted-foreground">관리자 권한이 필요합니다.</p>
      </div>
    );
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError("");
    try {
      await createUser.mutateAsync({
        username: newUsername,
        name: newName,
        email: newEmail || undefined,
        password: newPassword,
        role: newRole,
      });
      setShowCreate(false);
      setNewUsername("");
      setNewName("");
      setNewEmail("");
      setNewPassword("");
      setNewRole("user");
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : "생성에 실패했습니다.");
    }
  };

  const openEdit = (u: AdminUser) => {
    setEditTarget(u);
    setEditName(u.name);
    setEditEmail(u.email ?? "");
    setEditRole(u.role);
    setEditActive(u.is_active);
    setEditError("");
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editTarget) return;
    setEditError("");
    try {
      await updateUser.mutateAsync({
        id: editTarget.id,
        name: editName,
        email: editEmail || undefined,
        role: editRole,
        is_active: editActive,
      });
      setEditTarget(null);
    } catch (err) {
      setEditError(err instanceof Error ? err.message : "수정에 실패했습니다.");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteUser.mutateAsync(deleteTarget.id);
      setDeleteTarget(null);
    } catch {
      // error handled by mutation
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">사용자 관리</h2>
        <Button onClick={() => setShowCreate(true)} size="sm">
          <Plus className="mr-2 h-4 w-4" />
          사용자 추가
        </Button>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">로딩 중...</p>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">아이디</th>
                    <th className="px-4 py-3 text-left font-medium">이름</th>
                    <th className="px-4 py-3 text-left font-medium">이메일</th>
                    <th className="px-4 py-3 text-left font-medium">역할</th>
                    <th className="px-4 py-3 text-left font-medium">상태</th>
                    <th className="px-4 py-3 text-right font-medium">작업</th>
                  </tr>
                </thead>
                <tbody>
                  {data?.items.map((u) => (
                    <tr key={u.id} className="border-b last:border-0">
                      <td className="px-4 py-3 font-mono text-xs">{u.username}</td>
                      <td className="px-4 py-3">{u.name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{u.email ?? "-"}</td>
                      <td className="px-4 py-3">
                        <Badge variant={u.role === "admin" ? "default" : "secondary"}>
                          {u.role === "admin" ? "관리자" : "사용자"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        {u.is_active ? (
                          <Badge variant="outline" className="text-green-600 border-green-300">활성</Badge>
                        ) : (
                          <Badge variant="outline" className="text-red-600 border-red-300">비활성</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEdit(u)}
                            title="수정"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {u.id !== currentUser?.id && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteTarget(u)}
                              title="삭제"
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 사용자 추가 다이얼로그 */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>사용자 추가</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label>아이디</Label>
              <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} required placeholder="로그인에 사용할 아이디" />
            </div>
            <div className="space-y-2">
              <Label>이름</Label>
              <Input value={newName} onChange={(e) => setNewName(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label>이메일 (선택)</Label>
              <Input type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="연락용 이메일" />
            </div>
            <div className="space-y-2">
              <Label>비밀번호</Label>
              <Input type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required autoComplete="new-password" />
              <p className="text-xs text-muted-foreground">12자 이상, 대소문자+숫자+특수문자 포함</p>
            </div>
            <div className="space-y-2">
              <Label>역할</Label>
              <Select value={newRole} onValueChange={setNewRole}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">사용자</SelectItem>
                  <SelectItem value="admin">관리자</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {createError && <p className="text-sm text-destructive">{createError}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setShowCreate(false)}>취소</Button>
              <Button type="submit" disabled={createUser.isPending}>
                {createUser.isPending ? "생성 중..." : "생성"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 사용자 수정 다이얼로그 */}
      <Dialog open={!!editTarget} onOpenChange={(open) => !open && setEditTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>사용자 수정</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleEdit} className="space-y-4">
            <div className="space-y-2">
              <Label>아이디</Label>
              <Input value={editTarget?.username ?? ""} disabled className="bg-muted font-mono" />
            </div>
            <div className="space-y-2">
              <Label>이름</Label>
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} required />
            </div>
            <div className="space-y-2">
              <Label>이메일 (선택)</Label>
              <Input type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} placeholder="연락용 이메일" />
            </div>
            <div className="space-y-2">
              <Label>역할</Label>
              <Select value={editRole} onValueChange={setEditRole}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">사용자</SelectItem>
                  <SelectItem value="admin">관리자</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-3">
              <Label>계정 상태</Label>
              <Button
                type="button"
                variant={editActive ? "default" : "destructive"}
                size="sm"
                onClick={() => setEditActive(!editActive)}
              >
                {editActive ? (
                  <><ShieldCheck className="mr-1 h-4 w-4" />활성</>
                ) : (
                  <><ShieldOff className="mr-1 h-4 w-4" />비활성</>
                )}
              </Button>
            </div>
            {editError && <p className="text-sm text-destructive">{editError}</p>}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditTarget(null)}>취소</Button>
              <Button type="submit" disabled={updateUser.isPending}>
                {updateUser.isPending ? "저장 중..." : "저장"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* 삭제 확인 다이얼로그 */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>사용자 삭제</DialogTitle>
          </DialogHeader>
          <p className="text-sm">
            <strong>{deleteTarget?.name}</strong> (@{deleteTarget?.username})을 삭제하시겠습니까?
            이 작업은 되돌릴 수 없습니다.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>취소</Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteUser.isPending}>
              {deleteUser.isPending ? "삭제 중..." : "삭제"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
