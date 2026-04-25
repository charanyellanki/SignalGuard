import { Activity, AlertTriangle, BatteryLow, Building2, Wifi } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useFleetStats } from "@/hooks/useSites";

interface KpiProps {
  label: string;
  value: string;
  sub?: string;
  icon: JSX.Element;
  tone?: "neutral" | "good" | "warn" | "bad";
}

function tone(t: KpiProps["tone"]): string {
  switch (t) {
    case "good": return "text-emerald-500";
    case "warn": return "text-amber-500";
    case "bad":  return "text-destructive";
    default:     return "text-muted-foreground";
  }
}

function Kpi({ label, value, sub, icon, tone: t }: KpiProps): JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`shrink-0 ${tone(t)}`}>{icon}</div>
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {label}
          </div>
          <div className="font-mono text-2xl leading-tight tabular-nums">
            {value}
          </div>
          {sub ? (
            <div className="text-[11px] text-muted-foreground">{sub}</div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function KpiStrip(): JSX.Element {
  const { data, isLoading } = useFleetStats();

  const sites = data?.sites_count ?? 0;
  const total = data?.devices_total ?? 0;
  const online = data?.devices_online ?? 0;
  const anom = data?.anomalies_24h ?? 0;
  const lowBat = data?.low_battery_count ?? 0;

  const onlinePct = total > 0 ? (online / total) * 100 : 0;
  const onlineTone: KpiProps["tone"] =
    onlinePct >= 99 ? "good" : onlinePct >= 95 ? "warn" : "bad";

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-5">
      <Kpi
        label="Sites"
        value={isLoading ? "—" : String(sites)}
        icon={<Building2 className="h-5 w-5" />}
      />
      <Kpi
        label="Devices"
        value={isLoading ? "—" : total.toLocaleString()}
        sub="across the fleet"
        icon={<Activity className="h-5 w-5" />}
      />
      <Kpi
        label="Online"
        value={isLoading ? "—" : `${onlinePct.toFixed(1)}%`}
        sub={`${online.toLocaleString()} of ${total.toLocaleString()}`}
        icon={<Wifi className="h-5 w-5" />}
        tone={onlineTone}
      />
      <Kpi
        label="Anomalies (24h)"
        value={isLoading ? "—" : anom.toLocaleString()}
        icon={<AlertTriangle className="h-5 w-5" />}
        tone={anom > 50 ? "bad" : anom > 10 ? "warn" : "neutral"}
      />
      <Kpi
        label="Low battery"
        value={isLoading ? "—" : lowBat.toLocaleString()}
        sub="< 2.9 V — schedule swap"
        icon={<BatteryLow className="h-5 w-5" />}
        tone={lowBat > 0 ? "warn" : "good"}
      />
    </div>
  );
}
