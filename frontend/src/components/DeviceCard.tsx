import { Battery, BatteryLow, Signal, SignalLow, WifiOff } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { DeviceSummary } from "@/lib/types";

interface Props {
  device: DeviceSummary;
  onClick: () => void;
}

function batteryIcon(v: number | undefined): JSX.Element {
  if (v === undefined) return <Battery className="h-4 w-4 text-muted-foreground" />;
  return v < 2.9 ? (
    <BatteryLow className="h-4 w-4 text-destructive" />
  ) : (
    <Battery className="h-4 w-4 text-emerald-500" />
  );
}

function signalIcon(dbm: number | undefined): JSX.Element {
  if (dbm === undefined) return <Signal className="h-4 w-4 text-muted-foreground" />;
  return dbm <= -90 ? (
    <SignalLow className="h-4 w-4 text-destructive" />
  ) : (
    <Signal className="h-4 w-4 text-emerald-500" />
  );
}

export function DeviceCard({ device, onClick }: Props) {
  const t = device.latest;
  const hasAnom = device.anomaly_count > 0;
  const offline = !device.online;

  return (
    <Card
      className={`cursor-pointer transition-colors hover:border-primary/40 ${
        offline ? "border-destructive/40" : ""
      }`}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-mono">{device.device_id}</CardTitle>
          {offline ? (
            <Badge variant="destructive" className="gap-1">
              <WifiOff className="h-3 w-3" /> offline
            </Badge>
          ) : hasAnom ? (
            <Badge variant="destructive">{device.anomaly_count}</Badge>
          ) : (
            <Badge variant="success">ok</Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1.5">
            {batteryIcon(t?.battery_voltage)}
            <span className="font-mono">{t?.battery_voltage.toFixed(2) ?? "—"} V</span>
          </div>
          <div className="flex items-center gap-1.5">
            {signalIcon(t?.signal_strength_dbm)}
            <span className="font-mono">{t?.signal_strength_dbm.toFixed(0) ?? "—"} dBm</span>
          </div>
          <div className="col-span-2 font-mono">
            events: {t?.lock_events_count ?? 0} · {t?.temperature_c.toFixed(1) ?? "—"} °C
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
