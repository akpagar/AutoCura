
import { SimulationAPI } from "../services/endpoints";

export const SCENARIOS = [
  {
    key: "cpu",
    label: "CPU Overload",
    scenario: "cpu_overload",
    note: "Simulates high CPU usage",
    run: () => SimulationAPI.cpu(96),
  },
  {
    key: "memory",
    label: "Memory Exhaustion",
    scenario: "memory_exhaustion",
    note: "Simulates high memory usage",
    run: () => SimulationAPI.memory(92),
  },
  {
    key: "disk",
    label: "Disk Exhaustion",
    scenario: "disk_exhaustion",
    note: "Simulates disk exhaustion",
    run: () => SimulationAPI.disk(96),
  },
  {
    key: "network",
    label: "Network Degradation",
    scenario: "network_degradation",
    note: "Simulates network issues",
    run: () => SimulationAPI.network(800, 0.25),
  },
  {
    key: "service",
    label: "Service Failure",
    scenario: "service_failure",
    note: "Simulates service failure",
    run: () => SimulationAPI.serviceFailure(),
  },
];
