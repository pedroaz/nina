import * as vscode from "vscode";
import { NinaPanel } from "./NinaPanel";

export function addFileCommand(uri: vscode.Uri) {
  NinaPanel.webViewPanel.webview.postMessage({
    command: "addFile",
    data: uri,
  });
}
