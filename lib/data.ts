// Mock financial data for the Meridian planning platform.
// All figures are illustrative and generated deterministically.

export function formatCurrency(
  value: number,
  opts?: { compact?: boolean; sign?: boolean },
) {
  const { compact, sign } = opts ?? {};
  const abs = Math.abs(value);
  const prefix = sign && value > 0 ? "+" : value < 0 ? "-" : "";
  if (compact && abs >= 1000) {
    const units = [
      { v: 1e9, s: "B" },
      { v: 1e6, s: "M" },
      { v: 1e3, s: "K" },
    ];
    for (const u of units) {
      if (abs >= u.v) {
        return `${prefix}$${(abs / u.v).toFixed(abs / u.v >= 100 ? 0 : 1)}${u.s}`;
      }
    }
  }
  return `${prefix}$${abs.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function formatPercent(
  value: number,
  opts?: { sign?: boolean; digits?: number },
) {
  const { sign, digits = 1 } = opts ?? {};
  const prefix = sign && value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(digits)}%`;
}

export type Kpi = {
  id: string;
  label: string;
  value: string;
  raw: number;
  delta: number;
  deltaLabel: string;
  trend: "up" | "down";
  spark: number[];
  hint: string;
};

export const kpis: Kpi[] = [
  {
    id: "net-worth",
    label: "Net Worth",
    value: "$1,284,920",
    raw: 1284920,
    delta: 4.2,
    deltaLabel: "+$51,800 MTD",
    trend: "up",
    spark: [
      980, 1010, 1040, 1025, 1080, 1120, 1160, 1150, 1210, 1240, 1260, 1285,
    ],
    hint: "Assets minus liabilities across all linked accounts",
  },
  {
    id: "liquid",
    label: "Liquid Assets",
    value: "$342,150",
    raw: 342150,
    delta: 1.8,
    deltaLabel: "+$6,050 MTD",
    trend: "up",
    spark: [300, 305, 312, 318, 314, 322, 330, 328, 335, 338, 340, 342],
    hint: "Cash and cash-equivalent holdings available within 5 days",
  },
  {
    id: "monthly-cashflow",
    label: "Monthly Cash Flow",
    value: "+$8,420",
    raw: 8420,
    delta: -3.1,
    deltaLabel: "-$270 vs. avg",
    trend: "down",
    spark: [
      9200, 8900, 9100, 8700, 8800, 8600, 8900, 8500, 8420, 8700, 8600, 8420,
    ],
    hint: "Net of income and tracked recurring expenses",
  },
  {
    id: "savings-rate",
    label: "Savings Rate",
    value: "34.6%",
    raw: 34.6,
    delta: 2.4,
    deltaLabel: "+2.4 pts QoQ",
    trend: "up",
    spark: [28, 29, 30, 31, 30, 32, 33, 32, 34, 33, 34, 34.6],
    hint: "Share of after-tax income retained this quarter",
  },
];

export type NetWorthPoint = {
  month: string;
  assets: number;
  liabilities: number;
  net: number;
  projected?: boolean;
};

export const netWorthSeries: NetWorthPoint[] = (() => {
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  const base = 980000;
  return months.map((month, i) => {
    const assets = Math.round(base + i * 27000 + Math.sin(i / 1.6) * 18000);
    const liabilities = Math.round(210000 - i * 3200 + Math.cos(i / 2) * 4000);
    return { month, assets, liabilities, net: assets - liabilities };
  });
})();

export type AllocationSlice = {
  name: string;
  value: number;
  amount: number;
  color: string;
};

export const allocation: AllocationSlice[] = [
  { name: "Equities", value: 46, amount: 591063, color: "var(--chart-1)" },
  { name: "Fixed Income", value: 22, amount: 282682, color: "var(--chart-2)" },
  { name: "Real Estate", value: 18, amount: 231285, color: "var(--chart-3)" },
  { name: "Cash", value: 9, amount: 115642, color: "var(--chart-4)" },
  { name: "Alternatives", value: 5, amount: 64246, color: "var(--chart-5)" },
];

export type CashflowPoint = {
  month: string;
  income: number;
  expenses: number;
};

export const cashflowSeries: CashflowPoint[] = [
  { month: "Jul", income: 24200, expenses: 15300 },
  { month: "Aug", income: 24200, expenses: 16100 },
  { month: "Sep", income: 26800, expenses: 15900 },
  { month: "Oct", income: 24200, expenses: 14800 },
  { month: "Nov", income: 24200, expenses: 17200 },
  { month: "Dec", income: 28900, expenses: 18600 },
];

export type Account = {
  id: string;
  name: string;
  institution: string;
  type:
    | "Investment"
    | "Depository"
    | "Retirement"
    | "Credit"
    | "Loan"
    | "Property";
  mask: string;
  balance: number;
  change: number;
  apy?: number;
  status: "connected" | "attention" | "manual";
  updated: string;
};

export const accounts: Account[] = [
  {
    id: "a1",
    name: "Brokerage — Core",
    institution: "Fidelity",
    type: "Investment",
    mask: "4821",
    balance: 612480,
    change: 3.4,
    status: "connected",
    updated: "2m ago",
  },
  {
    id: "a2",
    name: "Roth IRA",
    institution: "Vanguard",
    type: "Retirement",
    mask: "9930",
    balance: 188220,
    change: 2.1,
    status: "connected",
    updated: "2m ago",
  },
  {
    id: "a3",
    name: "401(k) — Employer",
    institution: "Charles Schwab",
    type: "Retirement",
    mask: "1147",
    balance: 241900,
    change: 1.7,
    status: "connected",
    updated: "11m ago",
  },
  {
    id: "a4",
    name: "High-Yield Savings",
    institution: "Marcus",
    type: "Depository",
    mask: "5560",
    balance: 96400,
    change: 0.4,
    apy: 4.3,
    status: "connected",
    updated: "1h ago",
  },
  {
    id: "a5",
    name: "Primary Checking",
    institution: "Chase",
    type: "Depository",
    mask: "0042",
    balance: 28150,
    change: -1.2,
    status: "connected",
    updated: "4m ago",
  },
  {
    id: "a6",
    name: "Sapphire Reserve",
    institution: "Chase",
    type: "Credit",
    mask: "7781",
    balance: -8420,
    change: 0.0,
    status: "attention",
    updated: "9m ago",
  },
  {
    id: "a7",
    name: "Mortgage — 123 Elm St",
    institution: "Rocket",
    type: "Loan",
    mask: "3390",
    balance: -418600,
    change: -0.3,
    apy: 3.1,
    status: "manual",
    updated: "1d ago",
  },
  {
    id: "a8",
    name: "Residence — 123 Elm St",
    institution: "Manual",
    type: "Property",
    mask: "—",
    balance: 685000,
    change: 0.9,
    status: "manual",
    updated: "1d ago",
  },
];

export type Transaction = {
  id: string;
  date: string;
  merchant: string;
  category: string;
  account: string;
  amount: number;
  status: "cleared" | "pending";
};

export const transactions: Transaction[] = [
  {
    id: "t1",
    date: "Dec 18",
    merchant: "Dividend — VTI",
    category: "Investment Income",
    account: "Brokerage",
    amount: 1284.5,
    status: "cleared",
  },
  {
    id: "t2",
    date: "Dec 17",
    merchant: "Payroll — Acme Corp",
    category: "Salary",
    account: "Checking",
    amount: 12100.0,
    status: "cleared",
  },
  {
    id: "t3",
    date: "Dec 16",
    merchant: "Whole Foods Market",
    category: "Groceries",
    account: "Sapphire",
    amount: -218.34,
    status: "cleared",
  },
  {
    id: "t4",
    date: "Dec 16",
    merchant: "Mortgage Payment",
    category: "Housing",
    account: "Checking",
    amount: -3240.0,
    status: "pending",
  },
  {
    id: "t5",
    date: "Dec 15",
    merchant: "Transfer → Roth IRA",
    category: "Contribution",
    account: "Checking",
    amount: -583.0,
    status: "cleared",
  },
  {
    id: "t6",
    date: "Dec 14",
    merchant: "PG&E Utility",
    category: "Utilities",
    account: "Sapphire",
    amount: -186.2,
    status: "cleared",
  },
  {
    id: "t7",
    date: "Dec 13",
    merchant: "Delta Air Lines",
    category: "Travel",
    account: "Sapphire",
    amount: -642.8,
    status: "cleared",
  },
  {
    id: "t8",
    date: "Dec 12",
    merchant: "Interest — Marcus",
    category: "Interest Income",
    account: "Savings",
    amount: 342.11,
    status: "cleared",
  },
];

export type Milestone = {
  id: string;
  year: string;
  age: number;
  title: string;
  detail: string;
  amount: string;
  status: "done" | "active" | "upcoming";
};

export const milestones: Milestone[] = [
  {
    id: "m1",
    year: "2021",
    age: 30,
    title: "Emergency fund complete",
    detail: "6 months of expenses secured in HYSA",
    amount: "$96K",
    status: "done",
  },
  {
    id: "m2",
    year: "2024",
    age: 33,
    title: "Mortgage down payment",
    detail: "Purchased primary residence, 20% down",
    amount: "$137K",
    status: "done",
  },
  {
    id: "m3",
    year: "2026",
    age: 35,
    title: "Net worth crosses $1.5M",
    detail: "On track given current savings rate",
    amount: "$1.5M",
    status: "active",
  },
  {
    id: "m4",
    year: "2032",
    age: 41,
    title: "Children's education funded",
    detail: "529 plan target for two dependents",
    amount: "$420K",
    status: "upcoming",
  },
  {
    id: "m5",
    year: "2045",
    age: 54,
    title: "Coast FI reached",
    detail: "Portfolio self-sustains to retirement",
    amount: "$3.2M",
    status: "upcoming",
  },
  {
    id: "m6",
    year: "2055",
    age: 64,
    title: "Full retirement",
    detail: "Target withdrawal rate of 3.5%",
    amount: "$6.1M",
    status: "upcoming",
  },
];

export type Recommendation = {
  id: string;
  title: string;
  body: string;
  impact: string;
  impactValue: number;
  effort: "Low" | "Medium" | "High";
  category: string;
  confidence: number;
};

export const recommendations: Recommendation[] = [
  {
    id: "r1",
    title: "Increase 401(k) deferral to the annual max",
    body: "You are contributing 11% of $190K salary. Raising to 15% captures $7,600 more in tax-advantaged space this year and $2,100 in employer match you are leaving on the table.",
    impact: "+$9,700 / yr",
    impactValue: 9700,
    effort: "Low",
    category: "Retirement",
    confidence: 0.94,
  },
  {
    id: "r2",
    title: "Sweep idle checking cash into HYSA",
    body: "Primary Checking is holding $28,150 — roughly $16K above your 30-day spend buffer. Moving the excess to Marcus at 4.3% APY yields incremental interest with no liquidity impact.",
    impact: "+$690 / yr",
    impactValue: 690,
    effort: "Low",
    category: "Cash Management",
    confidence: 0.88,
  },
  {
    id: "r3",
    title: "Harvest losses in Fixed Income sleeve",
    body: "Two bond positions are down 6.2% YTD. Realizing $4,300 in losses offsets equity gains and can be reinvested into a comparable index to preserve allocation.",
    impact: "~$1,030 tax",
    impactValue: 1030,
    effort: "Medium",
    category: "Tax",
    confidence: 0.71,
  },
];

export type Scenario = {
  id: string;
  name: string;
  description: string;
  netWorthAt65: number;
  retirementAge: number;
  monthlyContribution: number;
  successRate: number;
  color: string;
  series: number[];
};

export const scenarios: Scenario[] = [
  {
    id: "s1",
    name: "Baseline",
    description: "Current savings rate and allocation held constant",
    netWorthAt65: 6100000,
    retirementAge: 64,
    monthlyContribution: 4200,
    successRate: 87,
    color: "var(--chart-4)",
    series: [1.28, 1.6, 2.0, 2.5, 3.1, 3.9, 4.8, 5.4, 6.1],
  },
  {
    id: "s2",
    name: "Aggressive Save",
    description: "Max all tax-advantaged accounts, +6% savings rate",
    netWorthAt65: 7850000,
    retirementAge: 59,
    monthlyContribution: 6100,
    successRate: 96,
    color: "var(--chart-1)",
    series: [1.28, 1.7, 2.3, 3.0, 3.9, 5.0, 6.2, 7.1, 7.85],
  },
  {
    id: "s3",
    name: "Early Exit",
    description: "Retire at 52 with a 3.25% withdrawal rate",
    netWorthAt65: 4900000,
    retirementAge: 52,
    monthlyContribution: 5200,
    successRate: 78,
    color: "var(--chart-3)",
    series: [1.28, 1.65, 2.15, 2.75, 3.4, 4.0, 4.4, 4.7, 4.9],
  },
];

export const scenarioYears = [
  "2026",
  "2030",
  "2035",
  "2040",
  "2045",
  "2050",
  "2055",
  "2060",
  "2065",
];

export type Insight = {
  id: string;
  kind: "observation" | "alert" | "opportunity";
  text: string;
  meta: string;
};

export const insights: Insight[] = [
  {
    id: "i1",
    kind: "opportunity",
    text: "Your savings rate rose 2.4 points this quarter — reallocating the surplus to equities would add an estimated $148K by retirement.",
    meta: "Based on 12-month contribution trend",
  },
  {
    id: "i2",
    kind: "alert",
    text: "Sapphire Reserve statement balance is up 34% month-over-month, driven mostly by Travel.",
    meta: "Anomaly detected vs. trailing 6 months",
  },
  {
    id: "i3",
    kind: "observation",
    text: "Equity exposure is 46%, roughly 4 points above your stated 42% target for this life stage.",
    meta: "Allocation drift since last rebalance",
  },
];
