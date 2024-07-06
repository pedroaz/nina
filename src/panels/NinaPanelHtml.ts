import * as vscode from "vscode";
import { getNonce } from "../lib/utils";

export function ninaHtml(webview: vscode.Webview, extensionUri: vscode.Uri) {
  // Local path to main script run in the webview
  const scriptPathOnDisk = vscode.Uri.joinPath(
    extensionUri,
    "out/compiled",
    "NinaApp.js"
  );

  // And the uri we use to load this script in the webview
  const scriptUri = webview.asWebviewUri(scriptPathOnDisk);

  // Local path to css styles
  // const styleResetPath = vscode.Uri.joinPath(
  //   this._extensionUri,
  //   "media",
  //   "reset.css"
  // );
  // const stylesPathMainPath = vscode.Uri.joinPath(
  //   this._extensionUri,
  //   "media",
  //   "vscode.css"
  // );

  // // Uri to load styles into webview
  // const stylesResetUri = webview.asWebviewUri(styleResetPath);
  // const stylesMainUri = webview.asWebviewUri(stylesPathMainPath);

  // Use a nonce to only allow specific scripts to be run
  const nonce = getNonce();

  return `<!DOCTYPE html>
			<html lang="en">
			<head>
				<meta charset="UTF-8">
        <meta http-equiv="Content-Security-Policy" content="default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'nonce-${nonce}'">
				<meta name="viewport" content="width=device-width, initial-scale=1.0">
				<title>Nina Explorer</title>
			</head>
			<body>
        <script nonce="${nonce}"=>
          const tsvscode = acquireVsCodeApi();
        </script>
				<script nonce="${nonce}" src="${scriptUri}"></script>
			</body>
			</html>`;
}
