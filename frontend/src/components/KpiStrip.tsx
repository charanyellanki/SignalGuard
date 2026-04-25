import { Activity, AlertTriangle, BatteryLow, Building2, DoorClosed, Flame, Users, Wifi } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useUnitsStats } from "@/hooks/useSites";

interface KpiProps {
  label: string;
  value: string;
  sub?: string;
  icon: JSX.Element;
  tone?: "neutral" | "good" | "warn" | "bad";
  emphasize?: boolean;
}

function tone(t: KpiProps["tone"]): string {
  switch (t) {
    case "good": return "text-emerald-500";
    case "warn": return "text-amber-500";
    case "bad":  return "text-destructive";
    default:     return "text-muted-foreground";
  }
}

function Kpi({ label, value, sub, icon, tone: t, emphasize }: KpiProps): JSX.Element {
  return (
    <Card className={emphasize ? "border-destructive/40 bg-destructive/5" : undefined}>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`shrink-0 ${tone(t)}`}>{icon}</div>
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wide text-muted-foreground">
            {label}
          </div>
          <div className={`font-mono leading-tight tabular-nums ${emphasize ? "text-3xl font-semibold" : "text-2xl"}`}>
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
  const { data, isLoading } = useUnitsStats();

  const customers = data?.customers_count ?? 0;
  const sites = data?.sites_count ?? 0;
  const total = data?.devices_total ?? 0;
  const online = data?.devices_online ?? 0;
  const tenantsImpacted = data?.tenants_impacted ?? 0;
  const openIncidents = data?.open_incidents ?? 0;
  const p0 = data?.p0_incidents ?? 0;
  const lowBat = data?.low_battery_count ?? 0;
  const anom24 = data?.anomalies_24h ?? 0;

  const tenantTone: KpiProps["tone"] =
    tenantsImpacted === 0 ? "good" : tenantsImpacted < 10 ? "warn" : "bad";

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
      <Kpi
        label="Tenants impacted"
        value={isLoading ? "—" : tenantsImpacted.toLocaleString()}
        sub="units currently offline"
        icon={<Users className="h-6 w-6" />}
        tone={tenantTone}
        emphasize={tenantsImpacted > 0}
      />
      <Kpi
        label="Open P0"
        value={isLoading ? "—" : p0.toLocaleString()}
        sub="high-severity unack'd"
        icon={<Flame className="h-5 w-5" />}
        tone={p0 > 0 ? "bad" : "good"}
      />
      <Kpi
        label="Open incidents"
        value={isLoading ? "—" : openIncidents.toLocaleString()}
        sub="any severity"
        icon={<AlertTriangle className="h-5 w-5" />}
        tone={openIncidents > 20 ? "bad" : openIncidents > 5 ? "warn" : "neutral"}
      />
      <Kpi
        label="Units online"
        value={isLoading ? "—" : `${online.toLocaleString()} / ${total.toLocaleString()}`}
        sub={total > 0 ? `${((online / total) * 100).toFixed(1)}%` : "—"}
        icon={<Wifi className="h-5 w-5" />}
        tone={total > 0 && online / total >= 0.99 ? "good" : "warn"}
      />
      <Kpi
        label="Customers"
        value={isLoading ? "—" : String(customers)}
        sub={`${sites} facilities`}
        icon={<Building2 className="h-5 w-5" />}
      />
      <Kpi
        label="Anomalies (24h)"
        value={isLoading ? "—" : anom24.toLocaleString()}
        icon={<Activity className="h-5 w-5" />}
        tone={anom24 > 50 ? "warn" : "neutral"}
      />
      <Kpi
        label="Low battery"
        value={isLoading ? "—" : lowBat.toLocaleString()}
        sub="< 2.9 V — schedule swap"
        icon={lowBat > 0 ? <BatteryLow className="h-5 w-5" /> : <DoorClosed className="h-5 w-5" />}
        tone={lowBat > 0 ? "warn" : "good"}
      />
    </div>
  );
}
