import { useState } from "react";
import { Building2, ChevronLeft, DoorClosed, Users } from "lucide-react";
import { Header } from "@/components/Header";
import { KpiStrip } from "@/components/KpiStrip";
import { CustomersOverview } from "@/components/CustomersOverview";
import { SitesOverview } from "@/components/SitesOverview";
import { DeviceGrid } from "@/components/DeviceGrid";
import { IncidentsQueue } from "@/components/IncidentsQueue";
import { DeviceDetail } from "@/components/DeviceDetail";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CustomerSummary, SiteSummary } from "@/lib/types";

type View = "customers" | "facilities" | "units";


export default function App(): JSX.Element {
  const [view, setView] = useState<View>("customers");
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerSummary | null>(null);
  const [selectedSite, setSelectedSite] = useState<SiteSummary | null>(null);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);

  const onPickCustomer = (c: CustomerSummary) => {
    setSelectedCustomer(c);
    setSelectedSite(null);
    setView("facilities");
  };

  const onPickSite = (s: SiteSummary) => {
    setSelectedSite(s);
    setView("units");
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header wsConnected={wsConnected} />

      <main className="container space-y-4 py-4">
        <KpiStrip />

        <div className="grid gap-4 md:grid-cols-[1fr_360px]">
          <section className="min-w-0 space-y-3">
            <Tabs value={view} onValueChange={(v) => setView(v as View)}>
              <div className="flex items-center justify-between">
                <TabsList>
                  <TabsTrigger value="customers" className="gap-1.5">
                    <Users className="h-3.5 w-3.5" /> Customers
                  </TabsTrigger>
                  <TabsTrigger value="facilities" className="gap-1.5">
                    <Building2 className="h-3.5 w-3.5" /> Facilities
                  </TabsTrigger>
                  <TabsTrigger value="units" className="gap-1.5">
                    <DoorClosed className="h-3.5 w-3.5" /> Units
                  </TabsTrigger>
                </TabsList>
                <ScopeBreadcrumb
                  customer={selectedCustomer}
                  site={selectedSite}
                  onClearCustomer={() => {
                    setSelectedCustomer(null);
                    setSelectedSite(null);
                  }}
                  onClearSite={() => setSelectedSite(null)}
                />
              </div>

              <TabsContent value="customers" className="mt-3">
                <CustomersOverview onSelect={onPickCustomer} />
              </TabsContent>

              <TabsContent value="facilities" className="mt-3 space-y-3">
                {selectedCustomer ? (
                  <ScopeHint
                    label="Customer"
                    value={selectedCustomer.customer_name}
                    onClear={() => setSelectedCustomer(null)}
                  />
                ) : null}
                <SitesOverview
                  customerId={selectedCustomer?.customer_id}
                  onSelect={onPickSite}
                />
              </TabsContent>

              <TabsContent value="units" className="mt-3 space-y-3">
                {selectedSite ? (
                  <ScopeHint
                    label="Facility"
                    value={selectedSite.site_name}
                    onClear={() => setSelectedSite(null)}
                  />
                ) : selectedCustomer ? (
                  <ScopeHint
                    label="Customer"
                    value={selectedCustomer.customer_name}
                    onClear={() => setSelectedCustomer(null)}
                  />
                ) : null}
                <DeviceGrid
                  customerId={selectedCustomer?.customer_id}
                  siteId={selectedSite?.site_id}
                  onSelect={setSelectedDeviceId}
                />
              </TabsContent>
            </Tabs>
          </section>

          <aside className="h-[calc(100vh-12rem)] md:sticky md:top-4">
            <IncidentsQueue
              onStatusChange={setWsConnected}
              onSelectDevice={setSelectedDeviceId}
            />
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

function ScopeBreadcrumb({
  customer,
  site,
  onClearCustomer,
  onClearSite,
}: {
  customer: CustomerSummary | null;
  site: SiteSummary | null;
  onClearCustomer: () => void;
  onClearSite: () => void;
}) {
  if (!customer && !site) return null;
  return (
    <div className="flex items-center gap-1 text-xs text-muted-foreground">
      {customer ? (
        <button
          className="rounded-md bg-muted px-2 py-0.5 hover:bg-muted/70"
          onClick={onClearCustomer}
          title="Clear customer filter"
        >
          {customer.customer_name} ✕
        </button>
      ) : null}
      {site ? (
        <button
          className="rounded-md bg-muted px-2 py-0.5 hover:bg-muted/70"
          onClick={onClearSite}
          title="Clear facility filter"
        >
          {site.site_name} ✕
        </button>
      ) : null}
    </div>
  );
}

function ScopeHint({
  label,
  value,
  onClear,
}: {
  label: string;
  value: string;
  onClear: () => void;
}) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <Button variant="ghost" size="sm" className="gap-1 px-2" onClick={onClear}>
        <ChevronLeft className="h-3.5 w-3.5" /> All
      </Button>
      <span className="text-muted-foreground">{label}:</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
