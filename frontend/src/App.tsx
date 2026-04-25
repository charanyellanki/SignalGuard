import { useState } from "react";
import { ChevronLeft, MapPin } from "lucide-react";
import { Header } from "@/components/Header";
import { KpiStrip } from "@/components/KpiStrip";
import { SitesOverview } from "@/components/SitesOverview";
import { DeviceGrid } from "@/components/DeviceGrid";
import { AnomalyFeed } from "@/components/AnomalyFeed";
import { DeviceDetail } from "@/components/DeviceDetail";
import { Button } from "@/components/ui/button";
import type { SiteSummary } from "@/lib/types";

export default function App(): JSX.Element {
  const [selectedSite, setSelectedSite] = useState<SiteSummary | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header wsConnected={wsConnected} />

      <main className="container space-y-4 py-4">
        <KpiStrip />

        <div className="grid gap-4 md:grid-cols-[1fr_320px]">
          <section className="min-w-0 space-y-3">
            {selectedSite ? (
              <>
                <div className="flex items-center justify-between">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSelectedSite(null)}
                    className="gap-1 px-2"
                  >
                    <ChevronLeft className="h-4 w-4" /> All sites
                  </Button>
                  <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <MapPin className="h-3.5 w-3.5" />
                    <span className="font-medium text-foreground">
                      {selectedSite.site_name}
                    </span>
                    <span className="font-mono text-xs">({selectedSite.site_id})</span>
                  </div>
                </div>
                <DeviceGrid
                  siteId={selectedSite.site_id}
                  onSelect={setSelectedDeviceId}
                />
              </>
            ) : (
              <>
                <div className="flex items-baseline justify-between">
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Sites
                  </h2>
                  <span className="text-xs text-muted-foreground">
                    Click a facility to drill into its devices
                  </span>
                </div>
                <SitesOverview onSelect={setSelectedSite} />
              </>
            )}
          </section>

          <aside className="h-[calc(100vh-12rem)] md:sticky md:top-4">
            <AnomalyFeed onStatusChange={setWsConnected} />
          </aside>
        </div>
      </main>

      <DeviceDetail
        deviceId={selectedDeviceId}
        open={selectedDeviceId !== null}
        onOpenChange={(o) => !o && setSelectedDeviceId(null)}
      />
    </div>
  );
}
