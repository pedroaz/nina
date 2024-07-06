import * as vscode from "vscode";
import { registerCommandHandlers } from "./lib/command-handlers";

export function activate(context: vscode.ExtensionContext) {
  console.log("Activating Nina Explorer extension");
  registerCommandHandlers(context);
}
export function deactivate() {}
