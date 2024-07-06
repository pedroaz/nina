import * as vscode from "vscode";
import { NinaPanel } from "../panels/NinaPanel";
import { ExtensionCommand } from "./commands";
import { addFileCommand as addFileCommand } from "../panels/panel-commands";

export const registerCommandHandlers = (context: vscode.ExtensionContext) => {
  context.subscriptions.push(
    vscode.commands.registerCommand(ExtensionCommand.ShowPanel, () => {
      NinaPanel.createOrShow(context.extensionUri);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(ExtensionCommand.RefreshPanel, () => {
      NinaPanel.kill();
      NinaPanel.createOrShow(context.extensionUri);
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand(
      ExtensionCommand.AddFileFromTree,
      (resource: vscode.Uri) => {
        addFileCommand(resource);
      }
    )
  );

  // TODO: Clean up this method
  context.subscriptions.push(
    vscode.commands.registerCommand(
      ExtensionCommand.AddFileFromMenuBar,
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
        } else {
          vscode.window.showInformationMessage("No file selected");
        }
      }
    )
  );
};
