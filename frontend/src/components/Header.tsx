import { useQuery } from "@tanstack/react-query";
import { Pause, Play } from "lucide-react";
import { api } from "@/lib/api";
import { useSimulationState, useSimulationToggle } from "@/hooks/useSimulation";

interface HeaderProps {
  wsConnected: boolean;
}

export function Header({ wsConnected }: HeaderProps) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 10_000,
  });

  const ok = health.data?.status === "ok" && wsConnected;

  const sim = useSimulationState();
  const toggleSim = useSimulationToggle();
  // Default to "running" when we don't yet have a confirmed state — keeps the
  // icon stable on first paint instead of flashing through Play→Pause.
  const simRunning = sim.data?.running ?? true;
  const simKnown = sim.data !== undefined;

  return (
    <header className="border-b border-border bg-card text-foreground">
      <div className="container flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img
            src="/noke_mark.png"
            alt="Nokē"
            className="h-10 w-10 select-none"
            draggable={false}
          />
          <div className="leading-none">
            <div className="flex items-end gap-1.5">
              <span className="text-2xl font-semibold tracking-tight text-primary">
                nokē
              </span>
              <span className="pb-0.5 text-sm font-medium leading-tight text-[hsl(var(--ring))]">
                smart<br />entry
              </span>
            </div>
          </div>
          <div className="ml-2 hidden h-9 border-l border-border/70 sm:block" />
          <div className="hidden leading-tight sm:block">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Operations Center
            </p>
            <p className="text-[11px] tracking-wide text-muted-foreground/80">
              Janus International · anomaly monitoring
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            role="status"
            className={
              ok
                ? "h-2.5 w-2.5 rounded-full bg-emerald-500 ring-2 ring-background"
                : "h-2.5 w-2.5 rounded-full bg-amber-500 ring-2 ring-background"
            }
            title={
              ok
                ? "All systems healthy"
                : "Degraded — API or real-time link unavailable"
            }
          />
          {/* Demo control — small and unobtrusive. Low opacity by default,
              full opacity on hover. Only renders once we know the simulator's
              actual state to avoid a misleading first paint. */}
          {simKnown ? (
            <button
              onClick={() => toggleSim.mutate(!simRunning)}
              disabled={toggleSim.isPending}
              aria-label={simRunning ? "Pause simulation" : "Resume simulation"}
              title={simRunning ? "Pause simulation" : "Resume simulation"}
              className="flex h-6 w-6 items-center justify-center rounded text-muted-foreground/70 transition-colors hover:text-foreground hover:bg-accent disabled:opacity-30"
            >
              {simRunning ? (
                <Pause className="h-3 w-3" />
              ) : (
                <Play className="h-3 w-3" />
              )}
            </button>
          ) : null}
        </div>
      </div>
    </header>
  );
}
