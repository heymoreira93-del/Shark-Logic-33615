import type { SupabaseClient } from "@supabase/supabase-js";
import type { Database } from "@/lib/supabase/database.types";
import type { TenantTable } from "./types";

type TypedClient = SupabaseClient<Database>;
type Tables = Database["public"]["Tables"];

function assertOrgId(organizationId: string) {
  if (!organizationId) {
    throw new Error("organizationId is required for tenant queries");
  }
}

// Loose builder: avoids Supabase generic select-string inference failures on dynamic tables.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyBuilder = any;

/**
 * Org-scoped query helpers. Always inject/filter organization_id.
 * RLS remains the hard security boundary; these prevent accidental cross-tenant bugs.
 */
export function tenantFrom<T extends TenantTable>(
  supabase: TypedClient,
  table: T,
  organizationId: string,
) {
  assertOrgId(organizationId);
  const from = supabase.from(table) as AnyBuilder;

  return {
    select(columns = "*", options?: { count?: "exact" | "planned" | "estimated"; head?: boolean }) {
      return from.select(columns, options).eq("organization_id", organizationId) as AnyBuilder;
    },
    insert(row: Omit<Tables[T]["Insert"], "organization_id"> | Omit<Tables[T]["Insert"], "organization_id">[]) {
      const rows = (Array.isArray(row) ? row : [row]).map((item) => ({
        ...item,
        organization_id: organizationId,
      }));
      return from.insert(rows) as AnyBuilder;
    },
    update(values: Omit<Tables[T]["Update"], "organization_id">) {
      return from.update(values).eq("organization_id", organizationId) as AnyBuilder;
    },
    delete() {
      return from.delete().eq("organization_id", organizationId) as AnyBuilder;
    },
  };
}

export function withOrgId<T extends Record<string, unknown>>(
  organizationId: string,
  row: T,
): T & { organization_id: string } {
  assertOrgId(organizationId);
  return { ...row, organization_id: organizationId };
}
