"use client";

import * as React from "react";
import { Activity, CheckCircle2, AlertCircle, RefreshCw, Database, Server } from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { HealthResponse, ReadinessResponse } from "@/lib/api/types";
import { config } from "@/lib/config";

type StatusState = "loading" | "connected" | "unavailable";

export function ApiStatusCard() {
  const [status, setStatus] = React.useState<StatusState>("loading");
  const [healthData, setHealthData] = React.useState<HealthResponse | null>(null);
  const [readinessData, setReadinessData] = React.useState<ReadinessResponse | null>(null);
  const [latencyMs, setLatencyMs] = React.useState<number | null>(null);
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = React.useState<boolean>(false);

  const probeBackend = React.useCallback(async () => {
    setIsRefreshing(true);
    setStatus("loading");
    setErrorMessage(null);

    const start = performance.now();
    let attempts = 0;
    const maxAttempts = 3;

    while (attempts < maxAttempts) {
      attempts++;
      try {
        // 1. Check process liveness with 90s tolerance for cold starts
        const health = await apiClient.checkHealth({ timeoutMs: 90000 });
        setHealthData(health);

        // 2. Check live PostgreSQL database readiness
        try {
          const ready = await apiClient.checkReadiness({ timeoutMs: 60000 });
          setReadinessData(ready);
        } catch {
          // Readiness can be degraded without failing process liveness
          setReadinessData(null);
        }

        setLatencyMs(Math.round(performance.now() - start));
        setStatus("connected");
        setErrorMessage(null);
        break;
      } catch (err: unknown) {
        if (attempts < maxAttempts) {
          // Wait 3 seconds before retrying (gives Render cold start time to finish booting)
          await new Promise((resolve) => setTimeout(resolve, 3000));
          continue;
        }

        setLatencyMs(Math.round(performance.now() - start));
        setHealthData(null);
        setReadinessData(null);
        setStatus("unavailable");

        const message =
          err instanceof Error
            ? err.message
            : "Unable to connect to the research assistant backend. The server may still be spinning up from cold sleep.";
        setErrorMessage(message);
      }
    }
    setIsRefreshing(false);
  }, []);


  React.useEffect(() => {
    probeBackend();
  }, [probeBackend]);

  return (
    <Card className="border-border/80 bg-card/60 backdrop-blur-md">
      <CardHeader className="p-5 pb-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 border border-primary/20 text-primary">
              <Server className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-sm font-semibold">FastAPI Backend Communication</CardTitle>
              <CardDescription className="text-xs">
                Centralized HTTP API client integration ({config.apiUrl})
              </CardDescription>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {status === "loading" && (
              <Badge variant="outline" className="gap-1 text-xs">
                <RefreshCw className="h-3 w-3 animate-spin text-muted-foreground" />
                <span>Checking API...</span>
              </Badge>
            )}
            {status === "connected" && (
              <Badge variant="success" className="gap-1 text-xs">
                <CheckCircle2 className="h-3 w-3" />
                <span>API connected</span>
              </Badge>
            )}
            {status === "unavailable" && (
              <Badge variant="destructive" className="gap-1 text-xs">
                <AlertCircle className="h-3 w-3" />
                <span>API unavailable</span>
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="p-5 pt-2 space-y-4">
        {status === "loading" && (
          <div className="py-4 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <RefreshCw className="h-4 w-4 animate-spin text-primary" />
            <span>Probing FastAPI health endpoints...</span>
          </div>
        )}

        {status === "connected" && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
              <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Liveness Probe
                </span>
                <p className="font-semibold text-foreground flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span>{healthData?.status || "healthy"}</span>
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">GET /api/v1/health</p>
              </div>

              <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  PostgreSQL Readiness
                </span>
                <p className="font-semibold text-foreground flex items-center gap-1.5">
                  <Database className="h-3.5 w-3.5 text-emerald-400" />
                  <span>{readinessData?.checks?.database?.status || "ready"}</span>
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">
                  {readinessData?.checks?.database?.name || "postgresql"} (SELECT 1)
                </p>
              </div>

              <div className="rounded-lg border border-border/50 bg-background/50 p-3 space-y-1">
                <span className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                  Client Latency
                </span>
                <p className="font-semibold text-foreground flex items-center gap-1.5">
                  <Activity className="h-3.5 w-3.5 text-indigo-400" />
                  <span>{latencyMs !== null ? `${latencyMs} ms` : "—"}</span>
                </p>
                <p className="text-[11px] font-mono text-muted-foreground">Round-trip time</p>
              </div>
            </div>
          </div>
        )}

        {status === "unavailable" && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 space-y-2 text-xs">
            <div className="flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <div className="space-y-1 flex-1">
                <p className="font-semibold text-destructive">API unavailable</p>
                <p className="text-muted-foreground leading-relaxed">
                  {errorMessage || "Unable to connect to the research assistant backend."}
                </p>
                <p className="text-[11px] text-muted-foreground/80 font-mono pt-1">
                  Target: {config.apiUrl}/api/v1/health
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-1 border-t border-border/40 text-xs">
          <span className="text-[11px] text-muted-foreground">
            FastAPI CORS configured for: <code className="text-foreground font-mono">http://localhost:3000</code>
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={probeBackend}
            isLoading={isRefreshing}
            className="h-7 text-xs gap-1.5"
          >
            <RefreshCw className="h-3 w-3" />
            <span>{status === "unavailable" ? "Retry Connection" : "Refresh Status"}</span>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
