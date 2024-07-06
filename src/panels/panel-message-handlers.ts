import { NinaPanel } from "./NinaPanel";
import * as vscode from "vscode";
import * as fs from "fs";
import * as path from "path";

export const registerMessageHandlers = (disposables: vscode.Disposable[]) => {
  NinaPanel.webViewPanel.webview.onDidReceiveMessage(
    (message) => {
      switch (message.command) {
        case "alert":
          handleAlert(message);
          return;
        case "open-file":
          handleOpenFile(message);
          return;
        case "persist-state":
          handlePersistState(message);
          return;
      }
    },
    null,
    disposables
  );
};

function handleAlert(message: any) {
  vscode.window.showErrorMessage(message.text);
}

function handleOpenFile(message: any) {
  vscode.workspace.openTextDocument(message.data.filePath).then((document) => {
    vscode.window.showTextDocument(document);
  });
}

function handlePersistState(message: any) {
  const projectRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
  if (!projectRoot) {
    return;
  }
  const directoryPath = path.join(projectRoot, ".nina");

  fs.mkdir(directoryPath, { recursive: true }, (err) => {
    if (err) {
      return console.error(`Error creating directory: ${err.message}`);
    }
  });

  const stateFilePath = path.join(directoryPath, "state.json");
  fs.writeFile(stateFilePath, JSON.stringify(message.data), (err) => {
    if (err) {
      return console.error(`Error writing file: ${err.message}`);
    }
  });
}
