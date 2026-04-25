import { useMemo } from "react";
import { AlertTriangle, BatteryLow, ChevronRight, Wifi, WifiOff } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useSites } from "@/hooks/useSites";
import type { SiteSummary } from "@/lib/types";

interface Props {
  customerId?: string | null;
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
  // If most of the site is offline, the LTE-M gateway has likely failed —
  // every tenant at that facility is currently locked out of their unit.
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
              {site.gateway_id ? ` · ${site.gateway_id}` : ""}
            </div>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </div>

        {wholeOffline ? (
          <div className="mb-3 flex items-center gap-1.5 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            <WifiOff className="h-3.5 w-3.5" />
            <span>Likely gateway outage — escalate to network ops</span>
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
              <span className="font-mono tabular-nums">{site.open_incidents}</span>
              <span className="ml-1 text-muted-foreground">open</span>
              <span className="ml-1.5 font-mono text-muted-foreground tabular-nums">· {site.anomalies_24h}</span>
              <span className="ml-1 text-muted-foreground">/ 24h</span>
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
              {offline} {offline === 1 ? "unit" : "units"} offline
            </span>
          ) : (
            "All units reporting"
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function SitesOverview({ customerId, onSelect }: Props): JSX.Element {
  const { data, isLoading, error } = useSites();

  const visible = useMemo(() => {
    if (!data) return [];
    if (!customerId) return data;
    return data.filter((s) => s.customer_id === customerId);
  }, [data, customerId]);

  // Group facilities under their operator when no specific customer is selected.
  const groups = useMemo(() => {
    const map = new Map<string, { name: string; sites: SiteSummary[] }>();
    for (const s of visible) {
      const key = s.customer_id ?? "_unknown";
      const name = s.customer_name ?? "Unassigned";
      const entry = map.get(key) ?? { name, sites: [] };
      entry.sites.push(s);
      map.set(key, entry);
    }
    return [...map.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name));
  }, [visible]);

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading facilities…</p>;
  }
  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>API unreachable</AlertTitle>
        <AlertDescription>{(error as Error).message}</AlertDescription>
      </Alert>
    );
  }
  if (visible.length === 0) {
    return (
      <Alert>
        <AlertTitle>No facilities yet</AlertTitle>
        <AlertDescription>
          {customerId
            ? "No facilities for this customer."
            : "Waiting for the simulator to publish telemetry — typically ~10s after boot."}
        </AlertDescription>
      </Alert>
    );
  }

  // Single-customer view: flat grid, no group headers.
  if (customerId) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((s) => (
          <SiteCard key={s.site_id} site={s} onClick={() => onSelect(s)} />
        ))}
      </div>
    );
  }

  // Multi-customer view: group by operator.
  return (
    <div className="space-y-5">
      {groups.map(([key, group]) => (
        <div key={key}>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {group.name}
            <span className="ml-2 font-mono text-[11px] normal-case tracking-normal text-muted-foreground/70">
              {group.sites.length} facilities
            </span>
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {group.sites.map((s) => (
              <SiteCard key={s.site_id} site={s} onClick={() => onSelect(s)} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
