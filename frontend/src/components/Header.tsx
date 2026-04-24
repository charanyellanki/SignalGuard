import { useQuery } from "@tanstack/react-query";
import { Activity, CircleCheck, CircleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

interface HeaderProps {
  deviceCount: number;
  anomalyCount: number;
  wsConnected: boolean;
}

export function Header({ deviceCount, anomalyCount, wsConnected }: HeaderProps) {
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
            Sentinel <span className="text-muted-foreground font-normal">— IoT anomaly detection</span>
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">{deviceCount} devices</Badge>
          <Badge variant={anomalyCount > 0 ? "destructive" : "secondary"}>
            {anomalyCount} anomalies
          </Badge>
          <Badge variant={ok ? "success" : "warning"} className="gap-1">
            {ok ? <CircleCheck className="h-3 w-3" /> : <CircleAlert className="h-3 w-3" />}
            {ok ? "healthy" : "degraded"}
          </Badge>
        </div>
      </div>
    </header>
  );
}
