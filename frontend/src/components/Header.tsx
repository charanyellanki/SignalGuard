import { useQuery } from "@tanstack/react-query";
import { CircleAlert, CircleCheck, Pause, Play } from "lucide-react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
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
    // Nokē brand surface: white canvas, dark-navy ink. Matches the
    // diamond mark's intended canvas (#0e1f3a navy + #00b4ff cyan).
    <header className="border-b border-border bg-white text-[#0e1f3a]">
      <div className="container flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img
            src="/noke_mark.png"
            alt="Signal Guard"
            className="h-10 w-10 select-none"
            draggable={false}
          />
          {/* Typographic wordmark to pair with the mark — replicates the
              official "nokē smart entry" lockup with the cyan accent. */}
          <div className="leading-none">
            <div className="flex items-end gap-1.5">
              <span className="text-2xl font-semibold tracking-tight text-[#0e1f3a]">
                nokē
              </span>
              <span className="pb-0.5 text-sm font-medium leading-tight text-[#00b4ff]">
                smart<br />entry
              </span>
            </div>
          </div>
          <div className="ml-2 hidden h-9 border-l border-[#0e1f3a]/15 sm:block" />
          <div className="hidden leading-tight sm:block">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#0e1f3a]/70">
              Operations Center
            </p>
            <p className="text-[11px] tracking-wide text-[#0e1f3a]/50">
              Janus HQ · multi-customer view
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={ok ? "success" : "warning"} className="gap-1">
            {ok ? <CircleCheck className="h-3 w-3" /> : <CircleAlert className="h-3 w-3" />}
            {ok ? "all systems healthy" : "degraded"}
          </Badge>
          {/* Demo control — small and unobtrusive. Low opacity by default,
              full opacity on hover. Only renders once we know the simulator's
              actual state to avoid a misleading first paint. */}
          {simKnown ? (
            <button
              onClick={() => toggleSim.mutate(!simRunning)}
              disabled={toggleSim.isPending}
              aria-label={simRunning ? "Pause simulation" : "Resume simulation"}
              title={simRunning ? "Pause simulation" : "Resume simulation"}
              className="flex h-6 w-6 items-center justify-center rounded text-[#0e1f3a]/30 transition-opacity hover:text-[#0e1f3a]/80 hover:bg-[#0e1f3a]/5 disabled:opacity-30"
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
