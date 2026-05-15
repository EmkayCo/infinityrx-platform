import type { PrescriberDirectoryClient } from "./client.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "./client.js";
import type {
  Npi,
  Prescriber,
  PrescriberSearchRequest,
  PrescriberSearchResponse,
} from "./types.js";

const MOCK_FIXTURE: Prescriber[] = [
  {
    npi: "1234567893",
    first_name: "Jane",
    last_name: "Smith",
    credential: "MD",
    primary_specialty: "Internal Medicine",
    state: "NY",
    zip: "10001",
    active: true,
  },
  {
    npi: "1987654320",
    first_name: "John",
    last_name: "Doe",
    credential: "DO",
    primary_specialty: "Family Medicine",
    state: "CA",
    zip: "90001",
    active: true,
  },
  {
    npi: "1112223334",
    first_name: "Maria",
    last_name: "Garcia",
    credential: "NP",
    primary_specialty: "Cardiology",
    state: "FL",
    zip: "33101",
    active: false,
  },
];

export function createMockPrescriberDirectoryClient(): PrescriberDirectoryClient {
  return {
    name: "prescriber-directory" as const,
    cachePolicies: PRESCRIBER_DIRECTORY_CACHE_POLICIES,

    async search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse> {
      const q = req.q.toLowerCase();
      const filtered = MOCK_FIXTURE.filter((p) => {
        const matchesQ =
          p.first_name.toLowerCase().includes(q) ||
          p.last_name.toLowerCase().includes(q) ||
          p.npi.includes(req.q);
        const matchesState = !req.state || p.state === req.state;
        const matchesSpecialty = !req.specialty || p.primary_specialty === req.specialty;
        return matchesQ && matchesState && matchesSpecialty;
      });
      return {
        results: filtered.slice(0, req.limit ?? 20),
        total: filtered.length,
      };
    },

    async getByNpi(npi: Npi): Promise<Prescriber | null> {
      return MOCK_FIXTURE.find((p) => p.npi === npi) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
