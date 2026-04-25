import { AlertTriangle, Building2, ChevronRight, Flame, Users, Wifi } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useCustomers } from "@/hooks/useCustomers";
import type { CustomerSummary } from "@/lib/types";

interface Props {
  onSelect: (customer: CustomerSummary) => void;
}

function CustomerCard({ customer, onClick }: { customer: CustomerSummary; onClick: () => void }) {
  const onlinePct = customer.device_count > 0
    ? (customer.devices_online / customer.device_count) * 100
    : 0;
  const isP0 = customer.p0_incidents > 0;
  const tenantsImpacted = customer.tenants_impacted;

  return (
    <Card
      className={`cursor-pointer transition-colors hover:border-primary/50 ${
        isP0 ? "border-destructive/50" : ""
      }`}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="mb-3 flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <img
              src="/noke_mark.png"
              alt=""
              aria-hidden
              className="h-7 w-7 shrink-0 select-none rounded-sm"
              draggable={false}
            />
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold">{customer.customer_name}</div>
              <div className="font-mono text-[11px] text-muted-foreground">
                {customer.customer_id} · Nokē-deployed
              </div>
            </div>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </div>

        {isP0 ? (
          <div className="mb-3 flex items-center gap-1.5 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-xs text-destructive">
            <Flame className="h-3.5 w-3.5" />
            <span>{customer.p0_incidents} P0 incident{customer.p0_incidents === 1 ? "" : "s"} open</span>
          </div>
        ) : null}

        {tenantsImpacted > 0 ? (
          <div className="mb-3 flex items-center gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-600 dark:text-amber-400">
            <Users className="h-3.5 w-3.5" />
            <span>{tenantsImpacted} tenant{tenantsImpacted === 1 ? "" : "s"} likely locked out</span>
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
          <div className="flex items-center gap-1.5">
            <Building2 className="h-3.5 w-3.5 text-muted-foreground" />
            <span>
              <span className="font-mono tabular-nums">{customer.facility_count}</span>
              <span className="ml-1 text-muted-foreground">facilities</span>
            </span>
          </div>
          <div className="flex items-center justify-end gap-1.5">
            <span className="text-muted-foreground">units</span>
            <span className="font-mono tabular-nums">{customer.device_count}</span>
          </div>

          <div className="flex items-center gap-1.5">
            <Wifi className="h-3.5 w-3.5 text-muted-foreground" />
            <Badge variant={onlinePct >= 99 ? "success" : onlinePct >= 95 ? "warning" : "destructive"}>
              {onlinePct.toFixed(1)}% online
            </Badge>
          </div>
          <div className="flex items-center justify-end gap-1.5">
            <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />
            <span>
              <span className="font-mono tabular-nums">{customer.open_incidents}</span>
              <span className="ml-1 text-muted-foreground">open</span>
            </span>
          </div>
        </div>

        <div className="mt-3 text-[11px] text-muted-foreground">
          {customer.anomalies_24h} anomalies in last 24h
        </div>
      </CardContent>
    </Card>
  );
}

export function CustomersOverview({ onSelect }: Props): JSX.Element {
  const { data, isLoading, error } = useCustomers();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading customers…</p>;
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
        <AlertTitle>No customers yet</AlertTitle>
        <AlertDescription>
          Waiting for the simulator to publish telemetry — typically ~10s after boot.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((c) => (
        <CustomerCard key={c.customer_id} customer={c} onClick={() => onSelect(c)} />
      ))}
    </div>
  );
}
