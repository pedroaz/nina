import * as vscode from "vscode";
import { getNonce } from "../lib/utils";
import { registerMessageHandlers } from "./panel-message-handlers";
import { ninaHtml } from "./NinaPanelHtml";
import * as fs from "fs";
import * as path from "path";

function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
  return {
    enableScripts: true,
    localResourceRoots: [
      vscode.Uri.joinPath(extensionUri, "media"),
      vscode.Uri.joinPath(extensionUri, "out/compiled"),
    ],
  };
}

export class NinaPanel {
  public static currentPanel: NinaPanel | undefined;

  public static readonly viewType = "nina";

  public static webViewPanel: vscode.WebviewPanel;
  private readonly _extensionUri: vscode.Uri;
  private _disposables: vscode.Disposable[] = [];

  private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    console.log("Constructor");
    NinaPanel.webViewPanel = panel;
    this._extensionUri = extensionUri;

    this.update();

    NinaPanel.webViewPanel.onDidDispose(
      () => this.dispose(),
      null,
      this._disposables
    );

    NinaPanel.webViewPanel.onDidChangeViewState(
      (e) => {
        if (NinaPanel.webViewPanel.visible) {
          this.update();
        }
      },
      null,
      this._disposables
    );

    registerMessageHandlers(this._disposables);
  }

  public static createOrShow(extensionUri: vscode.Uri) {
    console.log("Create or Show");
    const column = vscode.window.activeTextEditor
      ? vscode.window.activeTextEditor.viewColumn
      : undefined;

    // If we already have a panel, show it.
    if (NinaPanel.currentPanel) {
      NinaPanel.webViewPanel.reveal(column);
      return;
    }

    // Otherwise, create a new panel.
    const panel = vscode.window.createWebviewPanel(
      NinaPanel.viewType,
      "Nina",
      column || vscode.ViewColumn.One,
      getWebviewOptions(extensionUri)
    );

    NinaPanel.currentPanel = new NinaPanel(panel, extensionUri);
  }

  public static revive(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
    NinaPanel.currentPanel = new NinaPanel(panel, extensionUri);
  }

  public static kill() {
    NinaPanel.currentPanel?.dispose();
    NinaPanel.currentPanel = undefined;
  }

  public dispose() {
    NinaPanel.currentPanel = undefined;
    NinaPanel.webViewPanel.dispose();
    while (this._disposables.length) {
      const x = this._disposables.pop();
      if (x) {
        x.dispose();
      }
    }
  }

  private update() {
    console.log("Update");
    const webview = NinaPanel.webViewPanel.webview;
    const state = {
      name: "Pedro",
    };
    const projectRoot = vscode.workspace.workspaceFolders?.[0].uri.fsPath;
    if (!projectRoot) {
      return;
    }
    const directoryPath = path.join(projectRoot, ".nina");
    const stateFilePath = path.join(directoryPath, "state.json");
    if (fs.existsSync(stateFilePath)) {
      fs.readFile(stateFilePath, (err, data) => {
        if (err) {
          return console.error(`Error reading file: ${err.message}`);
        }
        const state = JSON.parse(data.toString());
        NinaPanel.webViewPanel.webview.postMessage({
          command: "render-state",
          data: state,
        });
      });
    }

    NinaPanel.webViewPanel.webview.html = ninaHtml(webview, this._extensionUri);
  }
}
