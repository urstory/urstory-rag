"use client";

import { useForm, useFieldArray } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import {
  useSettings,
  useUpdateSettings,
  useWatcherStatus,
  useStartWatcher,
  useStopWatcher,
  useScanWatcher,
} from "@/lib/queries";
import { toast } from "sonner";
import { Save, Plus, Trash2, Play, Square, RefreshCw } from "lucide-react";

const watcherSchema = z.object({
  enabled: z.boolean(),
  directories: z.array(z.object({ value: z.string().min(1) })),
  use_polling: z.boolean(),
  polling_interval: z.number().min(10).max(3600),
  auto_delete: z.boolean(),
  file_patterns: z.array(z.object({ value: z.string().min(1) })),
});

type WatcherFormData = z.infer<typeof watcherSchema>;

export function WatcherForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();
  const { data: watcherStatus } = useWatcherStatus();
  const startMutation = useStartWatcher();
  const stopMutation = useStopWatcher();
  const scanMutation = useScanWatcher();

  const form = useForm<WatcherFormData>({
    resolver: zodResolver(watcherSchema),
    values: {
      enabled: settings?.watcher?.enabled ?? false,
      directories: (settings?.watcher?.directories ?? []).map((d) => ({ value: d })),
      use_polling: settings?.watcher?.use_polling ?? false,
      polling_interval: settings?.watcher?.polling_interval ?? 60,
      auto_delete: settings?.watcher?.auto_delete ?? false,
      file_patterns: (settings?.watcher?.file_patterns ?? ["*.pdf", "*.docx", "*.txt", "*.md"]).map(
        (p) => ({ value: p }),
      ),
    },
  });

  const dirFields = useFieldArray({ control: form.control, name: "directories" });
  const patternFields = useFieldArray({ control: form.control, name: "file_patterns" });

  const onSubmit = async (data: WatcherFormData) => {
    try {
      await updateMutation.mutateAsync({
        watcher: {
          enabled: data.enabled,
          directories: data.directories.map((d) => d.value),
          use_polling: data.use_polling,
          polling_interval: data.polling_interval,
          auto_delete: data.auto_delete,
          file_patterns: data.file_patterns.map((p) => p.value),
        },
      });
      toast.success("감시 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  const handleStart = async () => {
    try {
      await startMutation.mutateAsync();
      toast.success("감시가 시작되었습니다.");
    } catch {
      toast.error("감시 시작에 실패했습니다.");
    }
  };

  const handleStop = async () => {
    try {
      await stopMutation.mutateAsync();
      toast.success("감시가 중지되었습니다.");
    } catch {
      toast.error("감시 중지에 실패했습니다.");
    }
  };

  const handleScan = async () => {
    try {
      await scanMutation.mutateAsync();
      toast.success("수동 스캔이 시작되었습니다.");
    } catch {
      toast.error("수동 스캔에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  const usePolling = form.watch("use_polling");
  const pollingInterval = form.watch("polling_interval");

  return (
    <div className="space-y-6">
      {/* Watcher Control */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>감시 상태</span>
            <Badge variant={watcherStatus?.status === "running" ? "default" : "outline"}>
              {watcherStatus?.status === "running" ? "실행 중" : "중지됨"}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleStart}
              disabled={startMutation.isPending || watcherStatus?.status === "running"}
            >
              <Play className="mr-2 h-4 w-4" />
              시작
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStop}
              disabled={stopMutation.isPending || watcherStatus?.status !== "running"}
            >
              <Square className="mr-2 h-4 w-4" />
              중지
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleScan}
              disabled={scanMutation.isPending}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              수동 스캔
            </Button>
          </div>
          {watcherStatus && (
            <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-3">
              <div>
                <p className="text-muted-foreground">감시 파일 수</p>
                <p className="font-medium">{watcherStatus.watched_file_count}</p>
              </div>
              <div>
                <p className="text-muted-foreground">동기화 완료</p>
                <p className="font-medium">{watcherStatus.stats.total_synced}</p>
              </div>
              <div>
                <p className="text-muted-foreground">대기 중</p>
                <p className="font-medium">{watcherStatus.stats.pending}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Watcher Settings */}
      <Card>
        <CardHeader>
          <CardTitle>감시 설정</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            <div className="flex items-center justify-between">
              <Label>감시 활성화</Label>
              <Switch
                checked={form.watch("enabled")}
                onCheckedChange={(v) => form.setValue("enabled", v)}
              />
            </div>

            <Separator />

            {/* Directories */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>감시 디렉토리</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => dirFields.append({ value: "" })}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  추가
                </Button>
              </div>
              {dirFields.fields.map((field, index) => (
                <div key={field.id} className="flex gap-2">
                  <Input
                    {...form.register(`directories.${index}.value`)}
                    placeholder="/data/documents"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => dirFields.remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            <Separator />

            {/* Watch mode */}
            <div className="space-y-2">
              <Label>감시 모드</Label>
              <Select
                value={usePolling ? "polling" : "event"}
                onValueChange={(v) => form.setValue("use_polling", v === "polling")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="event">이벤트 기반</SelectItem>
                  <SelectItem value="polling">폴링</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {usePolling && (
              <div className="space-y-2">
                <Label>폴링 간격: {pollingInterval}초</Label>
                <Slider
                  value={[pollingInterval]}
                  onValueChange={(v) => form.setValue("polling_interval", v[0])}
                  min={10}
                  max={3600}
                  step={10}
                />
              </div>
            )}

            <div className="flex items-center justify-between">
              <div>
                <Label>파일 삭제 시 자동 제거</Label>
                <p className="text-xs text-muted-foreground">
                  원본 파일 삭제 시 인덱스에서도 자동 제거
                </p>
              </div>
              <Switch
                checked={form.watch("auto_delete")}
                onCheckedChange={(v) => form.setValue("auto_delete", v)}
              />
            </div>

            <Separator />

            {/* File patterns */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>파일 패턴</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => patternFields.append({ value: "" })}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  추가
                </Button>
              </div>
              {patternFields.fields.map((field, index) => (
                <div key={field.id} className="flex gap-2">
                  <Input
                    {...form.register(`file_patterns.${index}.value`)}
                    placeholder="*.pdf"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => patternFields.remove(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            <Button type="submit" disabled={updateMutation.isPending}>
              <Save className="mr-2 h-4 w-4" />
              {updateMutation.isPending ? "저장 중..." : "저장"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
