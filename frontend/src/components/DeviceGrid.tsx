import { useDevices } from "@/hooks/useDevices";
import { DeviceCard } from "./DeviceCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface Props {
  onSelect: (deviceId: string) => void;
}

export function DeviceGrid({ onSelect }: Props) {
  const { data, isLoading, error } = useDevices();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading devices…</p>;
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
        <AlertTitle>No telemetry yet</AlertTitle>
        <AlertDescription>
          Waiting for the first messages to land — typically ~10s after boot.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
      {data.map((d) => (
        <DeviceCard key={d.device_id} device={d} onClick={() => onSelect(d.device_id)} />
      ))}
    </div>
  );
}
