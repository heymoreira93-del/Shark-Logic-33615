import { requirePageAuth } from "@/lib/authz";
import { CalculatorClient } from "./calculator-client";

export default async function CalculatorPage() {
  const ctx = await requirePageAuth("leads.edit");
  return <CalculatorClient canEdit={ctx.permissions.includes("leads.edit")} />;
}
