import { useMemo, useState } from "react";
import { Header } from "@/components/Header";
import { DeviceGrid } from "@/components/DeviceGrid";
import { AnomalyFeed } from "@/components/AnomalyFeed";
import { DeviceDetail } from "@/components/DeviceDetail";
import { useDevices } from "@/hooks/useDevices";

export default function App(): JSX.Element {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const devices = useDevices();

  const totals = useMemo(
    () => ({
      devices: devices.data?.length ?? 0,
      anomalies: devices.data?.reduce((n, d) => n + d.anomaly_count, 0) ?? 0,
    }),
    [devices.data],
  );

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header
        deviceCount={totals.devices}
        anomalyCount={totals.anomalies}
        wsConnected={wsConnected}
      />
      <main className="container grid gap-4 py-4 md:grid-cols-[1fr_320px]">
        <section>
          <DeviceGrid onSelect={setSelectedId} />
        </section>
        <aside className="h-[calc(100vh-5rem)] md:sticky md:top-4">
          <AnomalyFeed onStatusChange={setWsConnected} />
        </aside>
      </main>
      <DeviceDetail
        deviceId={selectedId}
        open={selectedId !== null}
        onOpenChange={(o) => !o && setSelectedId(null)}
      />
    </div>
  );
}
