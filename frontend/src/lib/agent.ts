"use client";

import { api, type Execution, type ScanReport } from "@/lib/api";

import type { AgentStep, ResultCardData } from "@/components/chat/execution-panel";

export interface AgentReply {
  message: string;
  steps: AgentStep[];
  result: ResultCardData | null;
  canExecute: boolean;
}

function step(
  id: string,
  title: string,
  description: string,
  status: AgentStep["status"] = "pending",
  output?: string,
): AgentStep {
  return { id, title, description, status, output };
}

function markDown(
  steps: AgentStep[],
  predicate: (s: AgentStep) => boolean,
): AgentStep[] {
  return steps.map((s) => ({ ...s, status: predicate(s) ? "done" : s.status }));
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function rankProtocol(protocol: string): string {
  return protocol.replace(/-/g, " ");
}

function describeScan(report: ScanReport): string {
  const lines: string[] = [];
  lines.push(
    `I analyzed **${report.recommendation_count}** candidate move${report.recommendation_count === 1 ? "" : "s"} across your positions under your current policy.`,
  );
  const allowed = report.recommendations.filter((r) => r.allowed);
  if (allowed.length > 0) {
    const best = allowed[0];
    lines.push(
      `**Best move:** move ${Number(best.amount).toLocaleString()} ${best.asset} from **${rankProtocol(best.current_protocol)}** to **${rankProtocol(best.opportunity.protocol)}** for **+${best.delta_apy.toFixed(2)}pp APY** (${best.opportunity.apy.toFixed(2)}% vs ${best.current_apy.toFixed(2)}%).`,
    );
    for (const rec of allowed.slice(1, 3)) {
      lines.push(
        `- Also actionable: ${rankProtocol(rec.current_protocol)} → ${rankProtocol(rec.opportunity.protocol)} on ${rec.asset} (+${rec.delta_apy.toFixed(2)}pp).`,
      );
    }
  } else {
    lines.push("No move currently clears your risk policy.");
  }
  if (report.blocked_count > 0) {
    lines.push(
      `${report.allowed_count} actionable, ${report.blocked_count} blocked by your policy rules.`,
    );
  }
  lines.push("Say **“move it”** or open a recommendation to execute the best one.");
  return lines.join("\n");
}

function stepsForScan(report: ScanReport): AgentStep[] {
  return [
    step("positions", "Loading tracked positions", "Reading active wallets and their yield positions.", "done"),
    step("market", "Fetching market data", "Querying live yield sources for each asset.", "done"),
    step("policy", "Evaluating policy", "Running every candidate through your risk rules.", "done"),
    step(
      "rank",
      "Ranking moves",
      `${report.allowed_count} allowed · ${report.blocked_count} blocked`,
      "done",
    ),
  ];
}

function stepsForExecution(action: { asset: string; amount: string }): AgentStep[] {
  return [
    step("wallet", "Confirming wallet", "Checking the wallet integration is configured.", "done"),
    step("policy", "Re-verifying policy", "Server re-checks this move before touching funds.", "done"),
    step("withdraw", "Withdrawing from source", `Exiting the current venue for ${action.asset}.`),
    step("supply", "Supplying to target", `Depositing ${action.asset} into the new venue.`),
    step("confirm", "Confirming on chain", "Polling the execution until it settles."),
  ];
}

export async function runAgent(input: string): Promise<AgentReply> {
  const text = input.toLowerCase();

  if (/(^|\s)(scan|analyze|check|find|opportunit)/.test(text)) {
    const steps: AgentStep[] = [
      step("positions", "Loading tracked positions", "Reading active wallets and their yield positions.", "active"),
      step("market", "Fetching market data", "Querying live yield sources for each asset."),
      step("policy", "Evaluating policy", "Running every candidate through your risk rules."),
    ];
    await pause(350);
    const report = await api.scan();
    const finalSteps = [
      ...markDown(steps, (s) => s.id === "positions"),
      step("market", "Fetching market data", "Querying live yield sources for each asset.", "done"),
      step("policy", "Evaluating policy", "Running every candidate through your risk rules.", "done"),
      step(
        "rank",
        "Ranking moves",
        `${report.allowed_count} allowed · ${report.blocked_count} blocked`,
        "done",
      ),
    ];
    const result: ResultCardData = {
      title: "Portfolio scan complete",
      subtitle: `${report.allowed_count} actionable move${report.allowed_count === 1 ? "" : "s"} found`,
      status: "completed",
      metrics: [
        { label: "Candidates", value: String(report.recommendation_count) },
        { label: "Allowed", value: String(report.allowed_count) },
        { label: "Blocked", value: String(report.blocked_count) },
        {
          label: "Best APY gain",
          value: report.recommendations.some((r) => r.allowed)
            ? `+${report.recommendations[0].delta_apy.toFixed(2)}pp`
            : "—",
        },
      ],
    };
    return {
      message: describeScan(report),
      steps: finalSteps,
      result,
      canExecute: report.allowed_count > 0,
    };
  }

  if (/(^|\s)(move|execute|do it|transfer)/.test(text)) {
    const report = await api.scan();
    const allowed = report.recommendations.filter((r) => r.allowed);
    if (allowed.length === 0) {
      return {
        message: "There are no policy-allowed moves right now, so there is nothing to execute. Run a **scan** to see why moves are blocked.",
        steps: [],
        result: null,
        canExecute: false,
      };
    }
    const rec = allowed[0];
    const wallets = await api.listWallets();
    const wallet = wallets.find((w) => w.address === rec.wallet_address);

    if (!wallet) {
      return {
        message: `I found a move for ${rec.asset} but the wallet **${rec.wallet_address}** is not registered with KeeperPilot. Connect it on the **Wallets** page first.`,
        steps: [],
        result: null,
        canExecute: false,
      };
    }

    const steps = stepsForExecution({ asset: rec.asset, amount: String(rec.amount) });
    steps[1] = { ...steps[1], status: "done" };
    await pause(250);
    const execution = await api.createExecution(
      wallet.id,
      rec.asset,
      rec.current_protocol,
      rec.opportunity.protocol,
    );

    const result: ResultCardData = {
      title: `${rec.asset} migration drafted`,
      subtitle: `${rankProtocol(rec.current_protocol)} → ${rankProtocol(rec.opportunity.protocol)}`,
      status: "submitted",
      metrics: [
        { label: "Amount", value: Number(rec.amount).toLocaleString() },
        { label: "Status", value: execution.status },
      ],
      primaryAction: {
        label: "Approve in Executions",
        onClick: () => {
          window.location.href = "/executions";
        },
      },
    };

    return {
      message:
        `I drafted the migration of **${Number(rec.amount).toLocaleString()} ${rec.asset}** ` +
        `from **${rankProtocol(rec.current_protocol)}** to **${rankProtocol(rec.opportunity.protocol)}** ` +
        `for **+${rec.delta_apy.toFixed(2)}pp APY**. ` +
        `Nothing moves without your approval — review it on the **Executions** page.`,
      steps: [
        ...steps.map((s) => ({ ...s, status: "done" as const })),
        step("draft", "Execution drafted", `${execution.status} · awaiting approval`, "done"),
      ],
      result,
      canExecute: false,
    };
  }

  if (/(^|\s)(positions|portfolio|holdings)/.test(text)) {
    const report = await api.scan();
    const positions = new Map<string, { protocol: string; asset: string; amount: string; apy: number; wallet: string }>();
    for (const rec of report.recommendations) {
      const key = `${rec.wallet_address}:${rec.current_protocol}:${rec.asset}`;
      positions.set(key, {
        protocol: rec.current_protocol,
        asset: rec.asset,
        amount: String(rec.amount),
        apy: rec.current_apy,
        wallet: rec.wallet_address,
      });
    }
    const lines = ["Here are the positions I can see across your wallets:"];
    for (const p of positions.values()) {
      lines.push(
        `- **${p.asset}** ${Number(p.amount).toLocaleString()} on **${rankProtocol(p.protocol)}** at **${p.apy.toFixed(2)}%**`,
      );
    }
    lines.push("The full breakdown is on the **Positions** page.");
    return {
      message: lines.join("\n"),
      steps: stepsForScan(report),
      result: null,
      canExecute: false,
    };
  }

  if (/(^|\s)(execution|history|activity)/.test(text)) {
    const executions: Execution[] = await api.listExecutions();
    if (executions.length === 0) {
      return {
        message: "You don't have any executions yet. Ask me to **scan** for opportunities and I'll draft a move for your approval.",
        steps: [],
        result: null,
        canExecute: false,
      };
    }
    const lines = [`You have **${executions.length}** execution${executions.length === 1 ? "" : "s"}:`];
    for (const e of executions.slice(0, 5)) {
      lines.push(`- **${e.asset ?? e.action}** · ${e.source_protocol ?? "?"} → ${e.target_protocol ?? "?"} · status: \`${e.status}\``);
    }
    return {
      message: lines.join("\n"),
      steps: [
        step("load", "Loading executions", "Fetching your execution history.", "done"),
      ],
      result: null,
      canExecute: false,
    };
  }

  if (/(^|\s)(policy|risk|settings|preferences)/.test(text)) {
    const prefs = await api.getPreferences();
    return {
      message:
        `Your current policy:\n` +
        `- **Risk tolerance:** ${prefs.risk_level}\n` +
        `- **Preferred assets:** ${prefs.preferred_assets.length ? prefs.preferred_assets.join(", ") : "any"}\n` +
        `- **Minimum APY gain:** ${prefs.minimum_yield_difference.toFixed(2)}pp\n` +
        `- **Max gas cost:** $${prefs.maximum_gas_cost.toFixed(2)}\n\n` +
        `Edit these on the **Policies** page.`,
      steps: [
        step("load", "Loading policy", "Fetching your risk preferences.", "done"),
      ],
      result: null,
      canExecute: false,
    };
  }

  return {
    message:
      "I'm your DeFi operator. Try:\n\n" +
      "- **“Scan my positions”** — evaluate every position for a better venue under your policy\n" +
      "- **“Move it”** — draft the best allowed migration for your approval\n" +
      "- **“What are my positions?”**, **“Show executions”**, or **“My policy”**\n\n" +
      "I never move funds without your explicit approval.",
    steps: [],
    result: null,
    canExecute: false,
  };
}

export { rankProtocol };
