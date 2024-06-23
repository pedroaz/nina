import * as vscode from "vscode";
import { NinaPanel } from "./NinaPanel";

export function activate(context: vscode.ExtensionContext) {
  console.log("NINA ACTIVATED");

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

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "nina-explorer.add-file-from-tree",
      (resource: vscode.Uri) => {
        NinaPanel.addFileCommand(resource);
      }
    )
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(
      "nina-explorer.add-file-from-top",
      async () => {
        const files = await vscode.workspace.findFiles(
          "**/*",
          "**/node_modules/**"
        );

        const fileItems = files.map((file) => ({
          label: vscode.workspace.asRelativePath(file),
          description: file.fsPath,
        }));

        const selectedFile = await vscode.window.showQuickPick(fileItems, {
          placeHolder: "Select a file",
        });

        if (selectedFile) {
          vscode.window.showInformationMessage(
            "Selected file: " + selectedFile.description
          );
          // Add your logic here to handle the file
        } else {
          vscode.window.showInformationMessage("No file selected");
        }
      }
    )
  );
}

// This method is called when your extension is deactivated
export function deactivate() {}
