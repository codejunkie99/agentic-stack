#!/usr/bin/env node

/**
 * agentic-stack MCP server — bridges the portable brain's Python CLI tools
 * into Gemini CLI's MCP tool registry.
 *
 * Transport: stdio (spawned by gemini-cli, communicates over stdin/stdout).
 * No network; no API keys. All state stays in .agent/ on disk.
 *
 * Install: the adapter's install.sh step writes this file and package.json
 * into <project>/.gemini/agentic-stack-mcp/ and appends an mcpServers entry
 * to <project>/.gemini/settings.json (or the user's global settings).
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { z } from "zod";

const execFileAsync = promisify(execFile);

const PROJECT_ROOT = process.env.AGENTIC_PROJECT_DIR || process.cwd();

function runPython(script, args, extraEnv) {
  return execFileAsync("python3", [script, ...args], {
    cwd: PROJECT_ROOT,
    timeout: 30000,
    env: { ...process.env, ...extraEnv },
  });
}

const server = new McpServer({
  name: "agentic-stack-connector",
  version: "0.1.0",
});

server.tool(
  "recall",
  "Surface graduated lessons from the agentic-stack portable brain relevant to an intent. Run BEFORE deploy, migration, debug, or refactor tasks.",
  { intent: z.string().describe("One-line description of the task about to be performed") },
  async ({ intent }) => {
    try {
      const { stdout, stderr } = await runPython(
        ".agent/tools/recall.py",
        [intent]
      );
      const text = (stdout || "").trim() || "(no lessons found)";
      return { content: [{ type: "text", text }] };
    } catch (err) {
      return {
        content: [{ type: "text", text: `recall failed: ${err.message}` }],
        isError: true,
      };
    }
  }
);

server.tool(
  "memory_reflect",
  "Log a significant event to the agentic-stack episodic memory. Use after completing a major feature, fixing a bug, making an architectural decision, or encountering a failure.",
  {
    skill: z.string().describe("Skill or domain name (e.g. deploy-checklist, git-proxy)"),
    action: z.string().describe("What was done"),
    outcome: z.string().describe("What happened — success message or error"),
    importance: z
      .number()
      .min(1)
      .max(10)
      .optional()
      .describe("1–10. 9–10: production incident / data migration. 7–8: deploy, schema change. 5–6: refactor, bug fix. 3–4: routine edit."),
    fail: z.boolean().optional().describe("Mark this as a failure event"),
    note: z.string().optional().describe("Free-text context — root cause, why it matters, what to remember"),
  },
  async (params) => {
    const args = [params.skill, params.action, params.outcome];
    if (params.importance != null) args.push("--importance", String(params.importance));
    if (params.fail) args.push("--fail");
    if (params.note) args.push("--note", params.note);
    try {
      const { stdout } = await runPython(".agent/tools/memory_reflect.py", args);
      return {
        content: [{ type: "text", text: (stdout || "").trim() || "event logged" }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `memory_reflect failed: ${err.message}` }],
        isError: true,
      };
    }
  }
);

server.tool(
  "learn",
  "Teach the agentic-stack a new rule in one shot (stage + graduate + render). Use when you discover something that should never happen again.",
  {
    rule: z.string().describe("The rule, phrased as a principle"),
    rationale: z.string().describe("Why — include the incident that taught you this"),
  },
  async ({ rule, rationale }) => {
    try {
      const { stdout } = await runPython(".agent/tools/learn.py", [
        rule,
        "--rationale",
        rationale,
      ]);
      return {
        content: [{ type: "text", text: (stdout || "").trim() || "rule learned" }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `learn failed: ${err.message}` }],
        isError: true,
      };
    }
  }
);

server.tool(
  "agentic_status",
  "Show a one-screen dashboard of the agentic-stack brain state: episodes, candidates, lessons, failing skills, activity graph.",
  {},
  async () => {
    try {
      const { stdout } = await runPython(".agent/tools/show.py", []);
      return {
        content: [{ type: "text", text: (stdout || "").trim() || "(no status available)" }],
      };
    } catch (err) {
      return {
        content: [{ type: "text", text: `status failed: ${err.message}` }],
        isError: true,
      };
    }
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
