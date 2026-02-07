// Modified: 2026-02-07T02:30:00Z | Author: COPILOT | Change: Add Athena Dashboard webview sidebar
import * as vscode from 'vscode';
import { registerSlateParticipant } from './slateParticipant';
import { registerSlateTools } from './tools';
import { SlateDashboardProvider } from './dashboardViewProvider';

export function activate(context: vscode.ExtensionContext) {
	registerSlateTools(context);
	registerSlateParticipant(context);

	// Register Athena Dashboard webview provider
	const dashboardProvider = new SlateDashboardProvider(context.extensionUri);
	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider(
			SlateDashboardProvider.viewType,
			dashboardProvider
		)
	);

	// Register commands
	context.subscriptions.push(
		vscode.commands.registerCommand('slate.showStatus', async () => {
			const terminal = vscode.window.createTerminal('SLATE Status');
			terminal.show();
			terminal.sendText(`"${getSlateConfig().pythonPath}" slate/slate_status.py --quick`);
		}),
		vscode.commands.registerCommand('slate.openDashboard', async () => {
			await vscode.commands.executeCommand('slate.dashboard.focus');
		}),
		vscode.commands.registerCommand('slate.refreshDashboard', async () => {
			await dashboardProvider.refresh();
		}),
		vscode.commands.registerCommand('slate.startDashboardServer', async () => {
			await dashboardProvider.startDashboardServer();
		})
	);
}

export function deactivate() { }

/** SLATE workspace configuration */
export interface SlateConfig {
	pythonPath: string;
	workspacePath: string;
}

/** Get SLATE configuration from workspace */
export function getSlateConfig(): SlateConfig {
	const workspaceFolders = vscode.workspace.workspaceFolders;
	const workspacePath = workspaceFolders?.[0]?.uri.fsPath ?? 'E:\\11132025';

	return {
		pythonPath: `${workspacePath}\\.venv\\Scripts\\python.exe`,
		workspacePath,
	};
}
