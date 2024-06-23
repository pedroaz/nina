import * as vscode from "vscode";
import { NinaPanel } from "./NinaPanel";

export function activate(context: vscode.ExtensionContext) {
  console.log('Congratulations, your extension "nina-explorer" is now active!');

  context.subscriptions.push(
    vscode.commands.registerCommand("nina-explorer.nina-show-panel", () => {
      NinaPanel.createOrShow(context.extensionUri);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("nina-explorer.nina-refresh-panel", () => {
      NinaPanel.kill();
      NinaPanel.createOrShow(context.extensionUri);
    })
  );
}

// This method is called when your extension is deactivated
export function deactivate() {}
