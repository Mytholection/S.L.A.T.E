// Modified: 2026-02-08T00:25:00Z | Author: COPILOT | Change: Simplified dashboard for debugging
import * as vscode from 'vscode';
import * as cp from 'child_process';
import { getSlateConfig } from './extension';
import { execSlateCommand } from './slateRunner';

export class SlateDashboardProvider implements vscode.WebviewViewProvider {
	public static readonly viewType = 'slate.dashboard';

	private _view?: vscode.WebviewView;
	private _refreshInterval?: NodeJS.Timeout;
	private _serverProcess?: cp.ChildProcess;

	constructor(private readonly _extensionUri: vscode.Uri) {}

	public resolveWebviewView(
		webviewView: vscode.WebviewView,
		context: vscode.WebviewViewResolveContext,
		_token: vscode.CancellationToken,
	) {
		console.log('[SLATE Dashboard] resolveWebviewView called');
		this._view = webviewView;

		webviewView.webview.options = {
			enableScripts: true,
			localResourceRoots: [this._extensionUri]
		};

		webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

		webviewView.webview.onDidReceiveMessage(async data => {
			console.log('[SLATE Dashboard] Message from webview:', data.type);
			switch (data.type) {
				case 'refresh':
					await this.refresh();
					break;
				case 'startServer':
					await this.startDashboardServer();
					break;
				case 'openBrowser':
					vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8080'));
					break;
			}
		});

		// Auto-refresh every 10 seconds
		this._refreshInterval = setInterval(() => {
			this.refresh();
		}, 10000);

		// Initial refresh
		this.refresh();
	}

	public async refresh() {
		if (!this._view) {
			return;
		}

		console.log('[SLATE Dashboard] Refresh started');

		try {
			const config = getSlateConfig();
			const token = new vscode.CancellationTokenSource().token;

			console.log('[SLATE Dashboard] Executing slate_status.py...');
			const statusResult = await execSlateCommand('slate/slate_status.py --json', token);
			const status = this._parseJSON(statusResult);

			console.log('[SLATE Dashboard] Executing slate_runtime.py...');
			const runtimeResult = await execSlateCommand('slate/slate_runtime.py --json', token);
			const runtime = this._parseJSON(runtimeResult);

			console.log('[SLATE Dashboard] Sending update message');
			this._view.webview.postMessage({
				type: 'updateStatus',
				status,
				runtime,
				timestamp: new Date().toISOString()
			});
		} catch (error) {
			console.error('[SLATE Dashboard] Refresh error:', error);
			if (this._view) {
				this._view.webview.postMessage({
					type: 'error',
					error: String(error)
				});
			}
		}
	}

	public async startDashboardServer() {
		if (this._serverProcess && !this._serverProcess.killed) {
			vscode.window.showInformationMessage('Dashboard server already running');
			return;
		}

		try {
			const config = getSlateConfig();

			this._serverProcess = cp.spawn(
				config.pythonPath,
				['agents/slate_dashboard_server.py'],
				{
					cwd: config.workspacePath,
					env: {
						...process.env,
						PYTHONPATH: config.workspacePath,
						PYTHONIOENCODING: 'utf-8'
					},
					stdio: 'ignore'
				}
			);

			vscode.window.showInformationMessage('Dashboard server started on port 8080');
		} catch (error) {
			vscode.window.showErrorMessage(`Error starting server: ${error}`);
		}
	}

	private _parseJSON(str: string): any {
		try {
			return JSON.parse(str);
		} catch {
			return null;
		}
	}

	private _getHtmlForWebview(webview: vscode.Webview) {
		const nonce = getNonce();

		return `<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>SLATE Dashboard</title>
	<style>
		* {
			margin: 0;
			padding: 0;
			box-sizing: border-box;
		}
		
		body {
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
			font-size: 13px;
			color: #e2e8f0;
			background: #0a0f1c;
			padding: 12px;
			line-height: 1.4;
		}
		
		.header {
			font-size: 16px;
			font-weight: 600;
			margin-bottom: 16px;
			padding-bottom: 8px;
			border-bottom: 1px solid #1e2d4a;
		}
		
		.card {
			background: rgba(15, 23, 41, 0.75);
			border: 1px solid #1e2d4a;
			border-radius: 6px;
			padding: 12px;
			margin-bottom: 12px;
		}
		
		.card-title {
			font-size: 12px;
			font-weight: 600;
			color: #f8fafc;
			margin-bottom: 8px;
		}
		
		.status-row {
			display: flex;
			justify-content: space-between;
			padding: 4px 0;
			font-size: 12px;
		}
		
		.badge {
			display: inline-block;
			padding: 2px 6px;
			border-radius: 3px;
			font-size: 11px;
			font-weight: 500;
		}
		
		.badge.ok {
			background: rgba(16, 185, 129, 0.2);
			color: #10b981;
			border: 1px solid rgba(16, 185, 129, 0.3);
		}
		
		.badge.error {
			background: rgba(239, 68, 68, 0.2);
			color: #ef4444;
			border: 1px solid rgba(239, 68, 68, 0.3);
		}
		
		.metrics {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 8px;
			margin-top: 8px;
		}
		
		.metric {
			background: rgba(59, 130, 246, 0.1);
			border: 1px solid rgba(59, 130, 246, 0.2);
			border-radius: 4px;
			padding: 8px;
			text-align: center;
		}
		
		.metric-value {
			font-size: 16px;
			font-weight: 700;
			color: #3b82f6;
			font-family: monospace;
		}
		
		.metric-label {
			font-size: 10px;
			color: #94a3b8;
			margin-top: 2px;
		}
		
		button {
			background: linear-gradient(135deg, #3b82f6, #06b6d4);
			border: none;
			color: white;
			padding: 8px 12px;
			border-radius: 4px;
			font-size: 11px;
			font-weight: 500;
			cursor: pointer;
			width: 100%;
			margin-top: 8px;
		}
		
		button:hover {
			opacity: 0.9;
		}
		
		.timestamp {
			text-align: center;
			font-size: 10px;
			color: #94a3b8;
			margin-top: 16px;
			font-family: monospace;
		}
	</style>
</head>
<body>
	<div class="header">⚡ SLATE Dashboard</div>
	
	<div id="content">
		<div style="text-align: center; color: #94a3b8; padding: 20px;">
			<div style="font-size: 14px; margin-bottom: 8px;">Loading...</div>
		</div>
	</div>
	
	<div class="timestamp" id="timestamp">Ready</div>

	<script nonce="${nonce}">
		const vscode = acquireVsCodeApi();
		
		console.log('[SLATE] Dashboard loaded');
		
		// Request initial refresh
		vscode.postMessage({ type: 'refresh' });
		
		// Handle messages from extension
		window.addEventListener('message', event => {
			console.log('[SLATE] Webview received:', event.data.type);
			
			if (event.data.type === 'updateStatus') {
				displayDashboard(event.data.status, event.data.runtime);
				if (event.data.timestamp) {
					document.getElementById('timestamp').textContent = 'Updated: ' + new Date(event.data.timestamp).toLocaleTimeString();
				}
			} else if (event.data.type === 'error') {
				document.getElementById('content').innerHTML = '<div class="card" style="color: #ef4444;">' + event.data.error + '</div>';
			}
		});
		
		// Button handlers
		document.addEventListener('click', e => {
			if (e.target.tagName === 'BUTTON') {
				const action = e.target.getAttribute('data-action');
				if (action === 'refresh') {
					vscode.postMessage({ type: 'refresh' });
				} else if (action === 'start') {
					vscode.postMessage({ type: 'startServer' });
				} else if (action === 'browser') {
					vscode.postMessage({ type: 'openBrowser' });
				}
			}
		});
		
		function displayDashboard(status, runtime) {
			console.log('[SLATE] Display dashboard - status:', !!status, 'runtime:', !!runtime);
			
			if (!status || !runtime) {
				document.getElementById('content').innerHTML = '<div class="card" style="color: #94a3b8;">Waiting for data...</div>';
				return;
			}
			
			const integrations = runtime.integrations || [];
			const getStatus = name => {
				const item = integrations.find(i => i.name.toLowerCase().includes(name.toLowerCase()));
				return item?.status === 'active';
			};
			
			let html = '';
			
			// System Health
			html += '<div class="card">';
			html += '<div class="card-title">System Health</div>';
			html += '<div class="status-row">';
			html += '<span>Python ' + (status.python?.version || 'N/A') + '</span>';
			html += '<span class="badge ' + (getStatus('python') ? 'ok' : 'error') + '">' + (getStatus('python') ? '✓' : '✗') + '</span>';
			html += '</div>';
			html += '<div class="status-row">';
			html += '<span>GPU (' + (status.gpu?.count || 0) + ')</span>';
			html += '<span class="badge ' + (getStatus('gpu') ? 'ok' : 'error') + '">' + (getStatus('gpu') ? '✓' : '✗') + '</span>';
			html += '</div>';
			html += '<div class="status-row">';
			html += '<span>PyTorch</span>';
			html += '<span class="badge ' + (getStatus('pytorch') ? 'ok' : 'error') + '">' + (getStatus('pytorch') ? '✓' : '✗') + '</span>';
			html += '</div>';
			html += '<div class="status-row">';
			html += '<span>Ollama (' + (status.ollama?.model_count || 0) + ' models)</span>';
			html += '<span class="badge ' + (getStatus('ollama') ? 'ok' : 'error') + '">' + (getStatus('ollama') ? '✓' : '✗') + '</span>';
			html += '</div>';
			html += '</div>';
			
			// System Metrics
			if (status.system) {
				html += '<div class="card">';
				html += '<div class="card-title">System Metrics</div>';
				html += '<div class="metrics">';
				html += '<div class="metric"><div class="metric-value">' + (status.system.cpu_count || 0) + '</div><div class="metric-label">CPU Cores</div></div>';
				html += '<div class="metric"><div class="metric-value">' + (status.system.cpu_percent?.toFixed(1) || 0) + '%</div><div class="metric-label">Usage</div></div>';
				html += '<div class="metric"><div class="metric-value">' + (status.system.memory_available_gb?.toFixed(1) || 0) + '</div><div class="metric-label">RAM (GB)</div></div>';
				html += '<div class="metric"><div class="metric-value">' + (status.system.disk_free_gb?.toFixed(0) || 0) + '</div><div class="metric-label">Disk (GB)</div></div>';
				html += '</div>';
				html += '</div>';
			}
			
			// GPU Details
			if (status.gpu && status.gpu.gpus && status.gpu.gpus.length > 0) {
				html += '<div class="card">';
				html += '<div class="card-title">GPU Info</div>';
				status.gpu.gpus.forEach(gpu => {
					html += '<div style="font-size: 11px; margin: 6px 0;">';
					html += '<strong>' + (gpu.name || 'GPU') + '</strong><br>';
					html += gpu.memory_total + ' (' + gpu.memory_free + ' free)';
					html += '</div>';
				});
				html += '</div>';
			}
			
			// Actions
			html += '<div class="card">';
			html += '<button data-action="start">🚀 Start Server</button>';
			html += '<button data-action="browser">🌐 Open Browser</button>';
			html += '<button data-action="refresh">🔄 Refresh</button>';
			html += '</div>';
			
			document.getElementById('content').innerHTML = html;
			console.log('[SLATE] Dashboard rendered successfully');
		}
	</script>
</body>
</html>`;
	}

	dispose() {
		if (this._refreshInterval) {
			clearInterval(this._refreshInterval);
		}
	}
}

function getNonce() {
	let text = '';
	const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
	for (let i = 0; i < 32; i++) {
		text += possible.charAt(Math.floor(Math.random() * possible.length));
	}
	return text;
}
