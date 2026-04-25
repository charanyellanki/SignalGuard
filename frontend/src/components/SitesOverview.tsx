import { AlertTriangle, BatteryLow, ChevronRight, Wifi, WifiOff } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useSites } from "@/hooks/useSites";
import type { SiteSummary } from "@/lib/types";

interface Props {
  onSelect: (site: SiteSummary) => void;
}

function onlineTone(pct: number): "success" | "warning" | "destructive" {
  if (pct >= 99) return "success";
  if (pct >= 95) return "warning";
  return "destructive";
}

function SiteCard({ site, onClick }: { site: SiteSummary; onClick: () => void }) {
  const onlinePct = site.device_count > 0 ? (site.devices_online / site.device_count) * 100 : 0;
  const offline = site.device_count - site.devices_online;
  const wholeOffline = onlinePct < 50;

  return (
    <Card
      className="cursor-pointer transition-colors hover:border-primary/50"
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold">{site.site_name}</div>
            <div className="font-mono text-[11px] text-muted-foreground">
              {site.site_id}
            </div>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </div>

        {wholeOffline ? (
          <div className="mb-3 flex items-center gap-1.5 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            <WifiOff className="h-3.5 w-3.5" />
            <span>Possible site gateway outage</span>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          <div className="flex items-center gap-1.5">
            <Wifi className="h-3.5 w-3.5 text-muted-foreground" />
            <Badge variant={onlineTone(onlinePct)}>
              {site.devices_online}/{site.device_count} online
            </Badge>
          </div>
          <div className="flex items-center justify-end gap-1.5 text-muted-foreground">
            <span className="font-mono tabular-nums">{onlinePct.toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />
            <span>
              <span className="font-mono tabular-nums">{site.anomalies_24h}</span>
              <span className="ml-1 text-muted-foreground">anomalies / 24h</span>
            </span>
          </div>
          <div className="flex items-center justify-end gap-1.5">
            <BatteryLow className="h-3.5 w-3.5 text-muted-foreground" />
            <span>
              <span className="font-mono tabular-nums">{site.low_battery_count}</span>
              <span className="ml-1 text-muted-foreground">low</span>
            </span>
          </div>
        </div>

        <div className="mt-3 text-[11px] text-muted-foreground">
          {offline > 0 ? (
            <span className="text-amber-500">
              {offline} {offline === 1 ? "device" : "devices"} offline
            </span>
          ) : (
            "All devices reporting"
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function SitesOverview({ onSelect }: Props): JSX.Element {
  const { data, isLoading, error } = useSites();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading sites…</p>;
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>API unreachable</AlertTitle>
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    );
  }
  if (!data || data.length === 0) {
    return (
      <Alert>
        <AlertTitle>No sites yet</AlertTitle>
        <AlertDescription>
          Waiting for the simulator to publish telemetry — typically ~10s after boot.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((s) => (
        <SiteCard key={s.site_id} site={s} onClick={() => onSelect(s)} />
      ))}
    </div>
  );
}
