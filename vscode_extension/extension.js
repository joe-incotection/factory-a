// Factory-A VS Code extension (shell / MVP).
// Surfaces the benefit (Verified / Blocked + plain reason); the internal pipeline
// stays hidden. Drives the engine as a subprocess — this is just the in-editor surface.
const vscode = require("vscode");
const cp = require("child_process");
const path = require("path");
const fs = require("fs");

let output;
let diagnostics; // DiagnosticCollection -> inline squiggles + Problems panel

function cfg() {
  const c = vscode.workspace.getConfiguration("factory-a");
  // Default to the engine bundled inside this extension (works out of the box,
  // hallucination check). Override via setting / env for the FULL engine.
  const home = c.get("home") || process.env.FACTORY_A_HOME || path.join(__dirname, "engine");
  return {
    home,
    python: c.get("pythonPath") || "python",
    profile: c.get("profile") || "general",
  };
}

function hasFullEngine() {
  const { home } = cfg();
  return fs.existsSync(path.join(home, "stage_tests", "gate_runner.py"));
}

function targetFolder() {
  // Prefer the active file's workspace folder; else the first workspace folder.
  const ed = vscode.window.activeTextEditor;
  if (ed) {
    const wf = vscode.workspace.getWorkspaceFolder(ed.document.uri);
    if (wf) return wf.uri.fsPath;
  }
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : undefined;
}

// Run run_gate.py with given extra args; stream to output; resolve exit code.
function runGate(extraArgs, title) {
  return new Promise((resolve) => {
    const { home, python, profile } = cfg();
    if (!home || !fs.existsSync(path.join(home, "run_gate.py"))) {
      vscode.window.showErrorMessage(
        "Factory-A: engine not found. Set 'factory-a.home' to the factory_a_pkg folder."
      );
      return resolve(-1);
    }
    const target = targetFolder();
    if (!target) {
      vscode.window.showErrorMessage("Factory-A: open a folder/workspace first.");
      return resolve(-1);
    }
    const args = [path.join(home, "run_gate.py"), target, "--profile", profile, ...extraArgs];
    output.clear();
    output.show(true);
    output.appendLine(`[Factory-A] ${title}`);
    output.appendLine(`$ ${python} run_gate.py ${target} --profile ${profile} ${extraArgs.join(" ")}`);
    output.appendLine("");

    const env = Object.assign({}, process.env, { PYTHONIOENCODING: "utf-8", FACTORY_A_HOME: home });
    const proc = cp.spawn(python, args, { cwd: home, env });
    proc.stdout.on("data", (d) => output.append(d.toString()));
    proc.stderr.on("data", (d) => output.append(d.toString()));
    proc.on("error", (e) => {
      vscode.window.showErrorMessage(`Factory-A: failed to launch python (${e.message}).`);
      resolve(-1);
    });
    proc.on("close", (code) => resolve(code));
  });
}

// Does this folder look like a Factory-A module (built from a spec)? The full gate
// is the QC step of a SPEC-FIRST pipeline — it needs a Golden I/O spec + golden tests,
// not arbitrary code. Bounded scan for GOLDEN_IO_LOCK*.yaml or test files.
function isFactoryModule(dir) {
  let found = false, count = 0;
  (function walk(d, depth) {
    if (found || depth > 4 || count > 1000) return;
    let entries;
    try { entries = fs.readdirSync(d, { withFileTypes: true }); } catch (e) { return; }
    for (const e of entries) {
      if (found) return;
      if (e.name === "node_modules" || e.name === "__pycache__" || e.name.startsWith(".")) continue;
      if (e.isDirectory()) { walk(path.join(d, e.name), depth + 1); continue; }
      count++;
      if (/GOLDEN_IO_LOCK/i.test(e.name) || /^test_.*\.py$/i.test(e.name) || /_test\.py$/i.test(e.name)) {
        found = true; return;
      }
    }
  })(dir, 0);
  return found;
}

async function verify() {
  if (!hasFullEngine()) {
    vscode.window.showInformationMessage(
      "Factory-A: full verify needs the full engine — set 'factory-a.home' to your factory_a_pkg folder. " +
      "The free hallucination check works now (Command Palette → Factory-A: Check for Hallucinated Names)."
    );
    return;
  }
  const tgt = targetFolder();
  if (tgt && !isFactoryModule(tgt)) {
    const pick = await vscode.window.showWarningMessage(
      "Factory-A is spec-first: the gate verifies a module you BUILD from a Factory-A spec (Golden I/O + " +
      "golden tests) — this folder has none yet. Start by adding the Master Guide, then have your AI write " +
      "the spec + code, then Verify.",
      "Add Master Guide"
    );
    if (pick === "Add Master Guide") await setupMaster();
    return;
  }
  const code = await runGate([], "Verifying folder (full gate)…");
  if (code === 0) vscode.window.showInformationMessage("✓ Factory-A: Verified — change passed the gate.");
  else if (code > 0) vscode.window.showErrorMessage("✗ Factory-A: Blocked — did not pass. See the Factory-A output for why.");
}

// Capture stdout (instead of streaming) — used for the --json diagnostics path.
function runGateCapture(extraArgs) {
  return new Promise((resolve) => {
    const { home, python, profile } = cfg();
    const target = targetFolder();
    if (!home || !target) return resolve({ code: -1, stdout: "", target });
    const args = [path.join(home, "run_gate.py"), target, "--profile", profile, ...extraArgs];
    const env = Object.assign({}, process.env, { PYTHONIOENCODING: "utf-8", FACTORY_A_HOME: home });
    const proc = cp.spawn(python, args, { cwd: home, env });
    let out = "";
    proc.stdout.on("data", (d) => (out += d.toString()));
    proc.on("error", () => resolve({ code: -1, stdout: "", target }));
    proc.on("close", (code) => resolve({ code, stdout: out, target }));
  });
}

async function checkHallucination() {
  diagnostics.clear();
  const { code, stdout, target } = await runGateCapture(["--halonly", "--json"]);
  if (code === -1) {
    vscode.window.showErrorMessage("Factory-A: engine not found / no folder. Set 'factory-a.home'.");
    return;
  }
  let res;
  try {
    res = JSON.parse(stdout.trim());
  } catch (e) {
    vscode.window.showErrorMessage("Factory-A: could not parse gate output. See Factory-A output.");
    output.appendLine(stdout);
    return;
  }
  const byFile = new Map();
  for (const d of res.diagnostics || []) {
    const uri = vscode.Uri.file(path.join(target, d.file));
    const line = Math.max(0, (d.line || 1) - 1);
    const col = Math.max(0, d.col || 0);
    const len = d.name ? d.name.length : 1;
    const range = new vscode.Range(line, col, line, col + len);
    const diag = new vscode.Diagnostic(range, d.message, vscode.DiagnosticSeverity.Error);
    diag.source = "Factory-A";
    if (!byFile.has(uri.fsPath)) byFile.set(uri.fsPath, { uri, items: [] });
    byFile.get(uri.fsPath).items.push(diag);
  }
  for (const { uri, items } of byFile.values()) diagnostics.set(uri, items);

  const n = (res.diagnostics || []).length;
  if (res.status === "FAIL" && n > 0) {
    vscode.window.showErrorMessage(`✗ Factory-A: ${n} hallucinated name(s) — see squiggles / Problems panel.`);
    vscode.commands.executeCommand("workbench.actions.view.problems");
  } else if (res.status === "PASS") {
    vscode.window.showInformationMessage("✓ Factory-A: No hallucinated names.");
  } else {
    vscode.window.showErrorMessage("Factory-A: check did not complete (engine/folder?).");
  }
}

// Drop the Master guide + a worked spec example into the user's folder, so their
// AI can read it and run the pipeline. (The guide ships inside the extension; the
// AI works in the user's workspace, so it must be copied there.)
async function setupMaster() {
  const target = targetFolder();
  if (!target) {
    vscode.window.showErrorMessage("Factory-A: open a folder/workspace first.");
    return;
  }
  try {
    fs.copyFileSync(path.join(__dirname, "FACTORY_A_START_HERE.md"),
                    path.join(target, "FACTORY_A_START_HERE.md"));
    fs.cpSync(path.join(__dirname, "assets", "factory_a_examples"),
              path.join(target, "factory_a_examples"), { recursive: true });
  } catch (e) {
    vscode.window.showErrorMessage(`Factory-A: could not write files (${e.message}).`);
    return;
  }
  const msg = "Read FACTORY_A_START_HERE.md and act as my Factory-A Master.";
  await vscode.env.clipboard.writeText(msg);
  const doc = await vscode.workspace.openTextDocument(path.join(target, "FACTORY_A_START_HERE.md"));
  await vscode.window.showTextDocument(doc);
  vscode.window.showInformationMessage(
    'Factory-A: Master guide + example added. Paste to your AI (copied to clipboard): "' + msg + '"'
  );
}

// Show MCP setup instructions — the bundled MCP server works with ANY client
// (Claude Code, Claude Desktop, Cursor, Codex CLI). We open the bundled README
// and copy the absolute path to server.py so the user can paste it into their
// client's mcpServers config.
async function showMcpSetup() {
  const serverPath = path.join(__dirname, "engine", "mcp_server", "server.py");
  const readmePath = path.join(__dirname, "engine", "mcp_server", "README.md");
  if (!fs.existsSync(serverPath) || !fs.existsSync(readmePath)) {
    vscode.window.showErrorMessage(
      "Factory-A: MCP server files not found in extension. Reinstall the extension."
    );
    return;
  }
  try {
    await vscode.env.clipboard.writeText(serverPath);
  } catch (e) {}
  try {
    const doc = await vscode.workspace.openTextDocument(readmePath);
    await vscode.window.showTextDocument(doc, { preview: false });
  } catch (e) {}
  vscode.window.showInformationMessage(
    "Factory-A MCP: server.py path copied to clipboard. Paste it into your AI client's " +
    "mcpServers config (Claude Code / Desktop / Cursor / Codex — see the README that just opened)."
  );
}

function activate(context) {
  output = vscode.window.createOutputChannel("Factory-A");
  diagnostics = vscode.languages.createDiagnosticCollection("factory-a");
  context.subscriptions.push(
    output,
    diagnostics,
    vscode.commands.registerCommand("factory-a.verify", verify),
    vscode.commands.registerCommand("factory-a.checkHallucination", checkHallucination),
    vscode.commands.registerCommand("factory-a.setupMaster", setupMaster),
    vscode.commands.registerCommand("factory-a.showMcpSetup", showMcpSetup)
  );
}

function deactivate() {}

module.exports = { activate, deactivate };
