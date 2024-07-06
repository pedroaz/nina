import { NinaPanel } from "./NinaPanel";
import * as vscode from "vscode";

export const registerMessageHandlers = (disposables: vscode.Disposable[]) => {
  NinaPanel.webViewPanel.webview.onDidReceiveMessage(
    (message) => {
      switch (message.command) {
        case "alert":
          vscode.window.showErrorMessage(message.text);
          return;
      }
    },
    null,
    disposables
  );

  NinaPanel.webViewPanel.webview.onDidReceiveMessage(
    (message) => {
      switch (message.command) {
        case "open-file":
          vscode.workspace
            .openTextDocument(message.data.filePath)
            .then((document) => {
              vscode.window.showTextDocument(document);
            });
          return;
      }
    },
    null,
    disposables
  );
};
