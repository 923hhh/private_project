"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { getMaintenanceToken } from "@/features/auth/lib/token-store";
import {
  isMaintenanceAuthExpiredError,
  listMaintenanceNotifications,
  markAllMaintenanceNotificationsRead,
  markMaintenanceNotificationRead,
  type MaintenanceNotificationItem,
} from "@/shared/lib/http";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";

export function NotificationMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<MaintenanceNotificationItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [submittingAll, setSubmittingAll] = useState(false);

  const unreadCount = useMemo(() => notifications.filter((item) => !item.read).length, [notifications]);

  useEffect(() => {
    if (!open) return;
    const token = getMaintenanceToken();
    if (!token) {
      setNotifications([]);
      return;
    }
    setLoading(true);
    void (async () => {
      try {
        const payload = await listMaintenanceNotifications(token, 12);
        setNotifications(payload.items);
      } catch (error) {
        if (isMaintenanceAuthExpiredError(error)) return;
        toast.error(error instanceof Error ? error.message : "加载通知失败");
      } finally {
        setLoading(false);
      }
    })();
  }, [open]);

  const handleOpenNotification = async (item: MaintenanceNotificationItem) => {
    const token = getMaintenanceToken();
    try {
      if (token && !item.read) {
        const updated = await markMaintenanceNotificationRead(token, item.id);
        setNotifications((current) => current.map((entry) => (entry.id === item.id ? updated : entry)));
      }
      if (item.link_url) {
        router.push(item.link_url);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "更新通知状态失败");
    }
  };

  const handleMarkAllRead = async () => {
    const token = getMaintenanceToken();
    if (!token || unreadCount === 0) return;
    setSubmittingAll(true);
    try {
      await markAllMaintenanceNotificationsRead(token);
      setNotifications((current) => current.map((item) => ({ ...item, read: true })));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "全部已读失败");
    } finally {
      setSubmittingAll(false);
    }
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="relative h-8 w-8 text-foreground/80 hover:bg-accent hover:text-foreground"
        >
          <Bell className="h-4 w-4" />
          {unreadCount > 0 ? <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-[#ef4444]" /> : null}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 border-border bg-popover p-1 text-popover-foreground">
        <div className="flex items-center justify-between px-2 py-1.5">
          <span className="text-xs text-muted-foreground">通知中心</span>
          <span className="text-[11px] text-muted-foreground">{unreadCount > 0 ? `${unreadCount} 条未读` : "已全部处理"}</span>
        </div>
        {loading ? (
          <div className="px-2 py-5 text-center text-xs text-muted-foreground">正在加载通知...</div>
        ) : notifications.length === 0 ? (
          <div className="px-2 py-5 text-center text-xs text-muted-foreground">当前没有新通知</div>
        ) : (
          notifications.map((item) => (
            <DropdownMenuItem
              key={item.id}
              className="flex flex-col items-start gap-0.5 rounded-md px-2 py-2 text-foreground focus:bg-accent focus:text-accent-foreground"
              onClick={() => void handleOpenNotification(item)}
            >
              <div className="flex w-full items-center justify-between gap-3">
                <span className="text-sm">{item.title}</span>
                {!item.read ? <span className="h-2 w-2 shrink-0 rounded-full bg-[#ef4444]" /> : null}
              </div>
              <span className="line-clamp-2 text-xs text-muted-foreground">{item.detail}</span>
            </DropdownMenuItem>
          ))
        )}
        <DropdownMenuSeparator className="bg-border" />
        <DropdownMenuItem
          className="text-center text-xs text-muted-foreground focus:bg-accent"
          onClick={() => void handleMarkAllRead()}
          disabled={submittingAll || unreadCount === 0}
        >
          全部标为已读
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
