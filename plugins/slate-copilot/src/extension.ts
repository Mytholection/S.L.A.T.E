// Modified: 2026-02-07T23:50:00Z | Author: COPILOT | Change: Force dashboard view to primary side bar
import * as vscode from 'vscode';
import { registerSlateParticipant } from './slateParticipant';
import { registerSlateTools } from './tools';
import { SlateDashboardProvider } from './dashboardViewProvider';

export function activate(context: vscode.ExtensionContext) {
	console.log('[SLATE] Extension activated');
	registerSlateTools(context);
	registerSlateParticipant(context);

	// Register Athena Dashboard webview provider
	const dashboardProvider = new SlateDashboardProvider(context.extensionUri);
	console.log('[SLATE] Dashboard provider registered');
	context.subscriptions.push(
		vscode.window.registerWebviewViewProvider(
			SlateDashboardProvider.viewType,
			dashboardProvider
		)
	);
	console.log('[SLATE] Dashboard view provider registered for viewType:', SlateDashboardProvider.viewType);

	// Register commands
	context.subscriptions.push(
		vscode.commands.registerCommand('slate.showStatus', async () => {
			const terminal = vscode.window.createTerminal('SLATE Status');
			terminal.show();
			terminal.sendText(`"${getSlateConfig().pythonPath}" slate/slate_status.py --quick`);
		}),
		vscode.commands.registerCommand('slate.openDashboard', async () => {
			console.log('[SLATE] slate.openDashboard command executed');
			try {
				// Show the SLATE Athena view container in the sidebar
				const result = await vscode.commands.executeCommand('workbench.view.extension.slate-athena');
				console.log('[SLATE] workbench.view.extension.slate-athena executed, result:', result);
			} catch (error) {
				console.error('[SLATE] Error opening dashboard:', error);
				vscode.window.showErrorMessage(`Failed to open dashboard: ${error}`);
			}
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
	if (!workspaceFolders || workspaceFolders.length === 0) {
		throw new Error('No workspace folder open. Please open the S.L.A.T.E workspace.');
	}

	const workspacePath = workspaceFolders[0].uri.fsPath;
	const fs = require('fs');
	const path = require('path');

	// Check for .venv in workspace
	const venvPath = path.join(workspacePath, '.venv', 'Scripts', 'python.exe');
	const pythonPath = fs.existsSync(venvPath) ? venvPath : 'python';

	return {
		pythonPath,
		workspacePath,
	};
}
