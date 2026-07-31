import { get, rootClient } from "./client";

import type {
  ComponentHealth,
  HealthData,
  ReadinessData,
  SystemMetricsRead,
  WorkersRead,
} from "@/types/domain";

export async function getSystemMetrics(): Promise<SystemMetricsRead> {
  return get<SystemMetricsRead>("/system/metrics");
}

export async function getSystemWorkers(): Promise<WorkersRead> {
  return get<WorkersRead>("/system/workers");
}

/** Liveness/health endpoints live outside /api/v1. */
export async function getHealth(): Promise<HealthData> {
  const response = await rootClient.get<HealthData>("/health");
  return response.data;
}

export async function getComponentHealth(
  component: "database" | "redis" | "storage" | "worker",
): Promise<ComponentHealth> {
  const response = await rootClient.get<ComponentHealth>(`/health/${component}`);
  return response.data;
}

export async function getReadiness(): Promise<ReadinessData> {
  const response = await rootClient.get<ReadinessData>("/health/ready");
  return response.data;
}

export const systemApi = {
  getSystemMetrics,
  getSystemWorkers,
  getHealth,
  getComponentHealth,
  getReadiness,
};
