import { useQuery } from "@tanstack/react-query";
import { Activity, CircleAlert, CircleCheck } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface HeaderProps {
  wsConnected: boolean;
}

export function Header({ wsConnected }: HeaderProps) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10_000,
  });

  const ok = health.data?.status === "ok" && wsConnected;

  return (
    <header className="border-b border-border bg-card/40 backdrop-blur">
      <div className="container flex h-14 items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity className="h-5 w-5 text-emerald-500" />
          <h1 className="text-base font-semibold tracking-tight">
            SignalGuard{" "}
            <span className="font-normal text-muted-foreground">
              — Noke fleet operations
            </span>
          </h1>
        </div>
        <Badge variant={ok ? "success" : "warning"} className="gap-1">
          {ok ? <CircleCheck className="h-3 w-3" /> : <CircleAlert className="h-3 w-3" />}
          {ok ? "all systems healthy" : "degraded"}
        </Badge>
      </div>
    </header>
  );
}
