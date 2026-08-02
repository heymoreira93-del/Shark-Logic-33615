/** Port of core Tampa MAO math for SaaS calculator (server + client safe). */

export type MaoInput = {
  arv: number;
  sqft: number;
  rehabLevel: "light" | "medium" | "heavy";
  fee?: number;
  closingCostPct?: number;
};

export type MaoResult = {
  arv: number;
  rehab: number;
  fee: number;
  closingCosts: number;
  mao: number;
  offerPrice: number;
};

const REHAB_PER_SQFT = {
  light: 15,
  medium: 30,
  heavy: 55,
} as const;

export function calculateMao(input: MaoInput): MaoResult {
  const arv = Math.max(0, Number(input.arv) || 0);
  const sqft = Math.max(0, Number(input.sqft) || 0);
  const fee = Math.max(0, Number(input.fee ?? 10000));
  const closingCostPct = Math.max(0, Number(input.closingCostPct ?? 0.05));
  const rehab = sqft * REHAB_PER_SQFT[input.rehabLevel];
  const closingCosts = arv * closingCostPct;
  const mao = arv * 0.7 - rehab - fee - closingCosts;
  const offerPrice = Math.max(0, Math.round(mao));
  return {
    arv,
    rehab: Math.round(rehab),
    fee,
    closingCosts: Math.round(closingCosts),
    mao: Math.round(mao),
    offerPrice,
  };
}
