// Modified: 2026-02-07T23:41:00Z | Author: COPILOT | Change: Fix dashboard button wiring
import * as vscode from 'vscode';
import * as cp from 'child_process';
import { getSlateConfig } from './extension';
import { execSlateCommand } from './slateRunner';

/**
 * SLATE Athena Dashboard Webview Provider
 * 
 * Provides a beautiful glassmorphism UI in the VS Code sidebar with:
 * - System status (GPU, CPU, memory, Python, PyTorch, Ollama)
 * - GitHub runner status and workflow runs
 * - Task queue management
 * - Real-time updates via WebSocket
 * 
 * Theme: Athena (Blue/cyan glassmorphism)
 */
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
		console.log('[SLATE Dashboard Provider] resolveWebviewView called');
		this._view = webviewView;

		webviewView.webview.options = {
			enableScripts: true,
			localResourceRoots: [this._extensionUri]
		};

		webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);
		console.log('[SLATE Dashboard Provider] HTML loaded, waiting for webview ready...');

		// Handle messages from the webview
		webviewView.webview.onDidReceiveMessage(async data => {
			console.log('[SLATE Dashboard Provider] Received message from webview:', data.type);
			switch (data.type) {
				case 'refresh':
					console.log('[SLATE Dashboard Provider] Handling refresh request...');
					await this.refresh();
					break;
				case 'startServer':
					console.log('[SLATE Dashboard Provider] Handling startServer request...');
					await this.startDashboardServer();
					break;
				case 'runCommand':
					console.log('[SLATE Dashboard Provider] Handling runCommand request...');
					await this.runCommand(data.command);
					break;
				case 'openBrowser':
					console.log('[SLATE Dashboard Provider] Opening browser...');
					vscode.env.openExternal(vscode.Uri.parse('http://127.0.0.1:8080'));
					break;
				default:
					console.log('[SLATE Dashboard Provider] Unknown message type:', data.type);
			}
		});

		// Auto-refresh every 10 seconds
		this._refreshInterval = setInterval(() => {
			console.log('[SLATE Dashboard Provider] Auto-refresh tick');
			this.refresh();
		}, 10000);

		// Initial load
		console.log('[SLATE Dashboard Provider] Calling initial refresh');
		this.refresh();
	}

	public async refresh() {
		if (!this._view) {
			return;
		}

		try {
			const token = new vscode.CancellationTokenSource().token;
			const config = getSlateConfig();

			console.log('[SLATE Dashboard] Starting refresh...');
			console.log('[SLATE Dashboard] Python path:', config.pythonPath);
			console.log('[SLATE Dashboard] Workspace path:', config.workspacePath);

			// Run status check
			console.log('[SLATE Dashboard] Executing slate_status.py...');
			const statusResult = await execSlateCommand('slate/slate_status.py --json', token);
			console.log('[SLATE Dashboard] Status result:', statusResult.substring(0, 200));

			console.log('[SLATE Dashboard] Executing slate_runtime.py...');
			const runtimeResult = await execSlateCommand('slate/slate_runtime.py --json', token);
			console.log('[SLATE Dashboard] Runtime result:', runtimeResult.substring(0, 200));

			const status = this._parseJSON(statusResult);
			const runtime = this._parseJSON(runtimeResult);

			console.log('[SLATE Dashboard] Parsed status:', status ? 'OK' : 'FAILED');
			console.log('[SLATE Dashboard] Parsed runtime:', runtime ? 'OK' : 'FAILED');

			this._view.webview.postMessage({
				type: 'updateStatus',
				status,
				runtime,
				timestamp: new Date().toISOString(),
				debug: {
					pythonPath: config.pythonPath,
					workspacePath: config.workspacePath,
					statusRaw: statusResult.substring(0, 500),
					runtimeRaw: runtimeResult.substring(0, 500)
				}
			});
		} catch (error) {
			console.error('[SLATE Dashboard] Refresh error:', error);
			if (this._view) {
				this._view.webview.postMessage({
					type: 'updateStatus',
					status: null,
					runtime: null,
					error: String(error),
					timestamp: new Date().toISOString()
				});
			}
		}
	}

	public async startDashboardServer() {
		if (this._serverProcess && !this._serverProcess.killed) {
			vscode.window.showInformationMessage('SLATE Dashboard server is already running');
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
						PYTHONIOENCODING: 'utf-8',
						CUDA_VISIBLE_DEVICES: '0,1',
						SLATE_WORKSPACE: config.workspacePath,
					},
					stdio: 'ignore',
					detached: false
				}
			);

			vscode.window.showInformationMessage('SLATE Dashboard server started on port 8080');
		} catch (error) {
			vscode.window.showErrorMessage(`Error starting dashboard: ${error}`);
		}
	}

	public async runCommand(command: string) {
		if (!this._view) {
			return;
		}

		try {
			const token = new vscode.CancellationTokenSource().token;
			const result = await execSlateCommand(command, token);

			this._view.webview.postMessage({
				type: 'commandResult',
				command,
				success: true,
				stdout: result
			});
		} catch (error) {
			this._view.webview.postMessage({
				type: 'commandResult',
				command,
				success: false,
				stderr: String(error)
			});
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
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}'; connect-src ws://127.0.0.1:8080 http://127.0.0.1:8080;">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>SLATE Athena Dashboard</title>
	<style>
		/* ═══════════════════════════════════════════════════════════════
		   SLATE Athena Theme — Blue/Cyan Glassmorphism
		   Modified: 2026-02-07T02:30:00Z | Author: COPILOT
		   ═══════════════════════════════════════════════════════════════ */
		:root {
			--bg-root: #0a0f1c;
			--bg-card: #0f1729;
			--bg-glass: rgba(15, 23, 41, 0.75);
			--bg-glass-hover: rgba(20, 30, 55, 0.85);
			--border: #1e2d4a;
			--border-active: #3b82f6;
			--text: #e2e8f0;
			--text-dim: #94a3b8;
			--text-bright: #f8fafc;
			--accent: #3b82f6;
			--accent2: #06b6d4;
			--success: #10b981;
			--error: #ef4444;
			--warning: #f59e0b;
			--font: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
			--mono: 'Cascadia Code', 'Fira Code', Consolas, monospace;
		}

		* {
			margin: 0;
			padding: 0;
			box-sizing: border-box;
		}

		body {
			font-family: var(--font);
			font-size: 13px;
			color: var(--text);
			background: var(--bg-root);
			padding: 12px;
			overflow-x: hidden;
		}

		/* ═══ Header ═══ */
		.header {
			text-align: center;
			padding: 16px 0;
			margin-bottom: 16px;
			border-bottom: 1px solid var(--border);
		}

		.header h1 {
			font-size: 20px;
			font-weight: 600;
			background: linear-gradient(135deg, var(--accent), var(--accent2));
			-webkit-background-clip: text;
			-webkit-text-fill-color: transparent;
			margin-bottom: 4px;
		}

		.header .subtitle {
			font-size: 11px;
			color: var(--text-dim);
			font-family: var(--mono);
		}

		/* ═══ Cards ═══ */
		.card {
			background: var(--bg-glass);
			backdrop-filter: blur(12px);
			border: 1px solid var(--border);
			border-radius: 8px;
			padding: 12px;
			margin-bottom: 12px;
			transition: all 0.2s ease;
		}

		.card:hover {
			background: var(--bg-glass-hover);
			border-color: var(--border-active);
		}

		.card-title {
			font-size: 12px;
			font-weight: 600;
			color: var(--text-bright);
			margin-bottom: 8px;
			display: flex;
			align-items: center;
			gap: 6px;
		}

		.card-title .icon {
			opacity: 0.7;
		}

		.card-content {
			font-size: 12px;
			color: var(--text);
		}

		/* ═══ Status Indicators ═══ */
		.status-row {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 6px 0;
			border-bottom: 1px solid rgba(30, 45, 74, 0.3);
		}

		.status-row:last-child {
			border-bottom: none;
		}

		.status-label {
			font-size: 11px;
			color: var(--text-dim);
		}

		.status-value {
			font-size: 12px;
			font-weight: 500;
			color: var(--text-bright);
			font-family: var(--mono);
		}

		.status-badge {
			display: inline-block;
			padding: 2px 8px;
			border-radius: 4px;
			font-size: 10px;
			font-weight: 600;
			text-transform: uppercase;
		}

		.status-badge.ok {
			background: rgba(16, 185, 129, 0.2);
			color: var(--success);
			border: 1px solid var(--success);
		}

		.status-badge.warn {
			background: rgba(245, 158, 11, 0.2);
			color: var(--warning);
			border: 1px solid var(--warning);
		}

		.status-badge.error {
			background: rgba(239, 68, 68, 0.2);
			color: var(--error);
			border: 1px solid var(--error);
		}

		.status-detail {
			font-size: 10px;
			color: var(--text-dim);
			font-family: var(--mono);
			margin-left: auto;
			padding-left: 8px;
		}

		/* ═══ Buttons ═══ */
		.btn {
			background: var(--bg-glass);
			border: 1px solid var(--border);
			color: var(--text);
			padding: 8px 12px;
			border-radius: 6px;
			font-size: 11px;
			font-weight: 500;
			cursor: pointer;
			transition: all 0.2s ease;
			font-family: var(--font);
			width: 100%;
			margin-top: 8px;
		}

		.btn:hover {
			background: var(--accent);
			border-color: var(--accent);
			color: var(--text-bright);
			transform: translateY(-1px);
		}

		.btn:active {
			transform: translateY(0);
		}

		.btn-primary {
			background: linear-gradient(135deg, var(--accent), var(--accent2));
			border: none;
			color: white;
		}

		.btn-primary:hover {
			opacity: 0.9;
			transform: translateY(-1px);
		}

		/* ═══ Loading ═══ */
		.loading {
			text-align: center;
			padding: 24px;
			color: var(--text-dim);
		}

		.spinner {
			border: 2px solid var(--border);
			border-top: 2px solid var(--accent);
			border-radius: 50%;
			width: 24px;
			height: 24px;
			animation: spin 1s linear infinite;
			margin: 0 auto 8px;
		}

		@keyframes spin {
			0% { transform: rotate(0deg); }
			100% { transform: rotate(360deg); }
		}

		/* ═══ Metric Grid ═══ */
		.metric-grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 8px;
			margin-top: 8px;
		}

		.metric {
			background: rgba(59, 130, 246, 0.1);
			border: 1px solid rgba(59, 130, 246, 0.3);
			border-radius: 6px;
			padding: 8px;
			text-align: center;
		}

		.metric-value {
			font-size: 18px;
			font-weight: 700;
			color: var(--accent);
			font-family: var(--mono);
		}

		.metric-label {
			font-size: 10px;
			color: var(--text-dim);
			margin-top: 2px;
		}

		/* ═══ GPU Status ═══ */
		.gpu-item {
			background: rgba(6, 182, 212, 0.1);
			border: 1px solid rgba(6, 182, 212, 0.3);
			border-radius: 6px;
			padding: 8px;
			margin-top: 6px;
		}

		.gpu-name {
			font-size: 11px;
			font-weight: 600;
			color: var(--accent2);
		}

		.gpu-memory {
			font-size: 10px;
			color: var(--text-dim);
			font-family: var(--mono);
			margin-top: 2px;
		}

		/* ═══ Timestamp ═══ */
		.timestamp {
			text-align: center;
			font-size: 10px;
			color: var(--text-dim);
			padding: 8px 0;
			font-family: var(--mono);
		}
	</style>
</head>
<body>
	<div class="header">
		<h1>⚡ SLATE Athena</h1>
		<div class="subtitle">System Learning Agent for Task Execution</div>
	</div>

	<div id="content">
		<div class="loading">
			<div class="spinner"></div>
			<div>Loading SLATE status...</div>
		</div>
	</div>

	<div class="timestamp" id="timestamp">Last updated: --</div>

	<script nonce="${nonce}">
		const vscode = acquireVsCodeApi();

		console.log('[SLATE Dashboard Webview] Initialized');

		// Request initial refresh
		console.log('[SLATE Dashboard Webview] Requesting initial refresh...');
		vscode.postMessage({ type: 'refresh' });

		// Handle messages from extension
		window.addEventListener('message', event => {
			const message = event.data;
			console.log('[SLATE Dashboard Webview] Received message:', message.type);

			switch (message.type) {
				case 'updateStatus':
					console.log('[SLATE Dashboard Webview] Rendering status...');
					renderStatus(message.status, message.runtime, message.timestamp, message.error, message.debug);
					break;
				case 'commandResult':
					console.log('[SLATE Dashboard Webview] Handling command result...');
					handleCommandResult(message);
					break;
				default:
					console.log('[SLATE Dashboard Webview] Unknown message type:', message.type);
			}
		});

		document.addEventListener('click', event => {
			const target = event.target instanceof HTMLElement
				? event.target.closest('button[data-action]')
				: null;
			if (!target) {
				return;
			}

			const action = target.getAttribute('data-action');
			switch (action) {
				case 'refresh':
					refresh();
					break;
				case 'startServer':
					startDashboard();
					break;
				case 'openBrowser':
					openBrowser();
					break;
				default:
					console.log('[SLATE Dashboard Webview] Unknown action:', action);
			}
		});

		function renderStatus(status, runtime, timestamp, error, debug) {
			const content = document.getElementById('content');
			
			if (error) {
				content.innerHTML = \`
					<div class="card">
						<div class="card-title" style="color: var(--error);">
							<span class="icon">⚠️</span>
							Error Loading Status
						</div>
						<div class="card-content" style="color: var(--error); font-family: monospace; font-size: 12px; white-space: pre-wrap;">
							\${error}
						</div>
					</div>
				\`;
				return;
			}
			
			if (!status || !runtime) {
				const debugInfo = debug ? \`
					<div class="card">
						<div class="card-title">Debug Info</div>
						<div class="card-content" style="font-family: monospace; font-size: 11px; white-space: pre-wrap;">
Python: \${debug.pythonPath || 'unknown'}
Workspace: \${debug.workspacePath || 'unknown'}

Status output:
\${debug.statusRaw || 'none'}

Runtime output:
\${debug.runtimeRaw || 'none'}
						</div>
					</div>
				\` : '';
				content.innerHTML = \`
					<div class="card">
						<div class="card-content" style="color: var(--warn);">
							Failed to parse SLATE status. Check Python installation and workspace paths.
						</div>
					</div>
					\${debugInfo}
				\`;
				return;
			}

			// Parse runtime integrations array
			const integrations = runtime.integrations || [];
			const getIntegration = (name) => integrations.find(i => i.name.toLowerCase().includes(name.toLowerCase()));
			
			const pythonOk = getIntegration('python')?.status === 'active';
			const venvOk = getIntegration('virtual env')?.status === 'active';
			const gpuOk = getIntegration('gpu')?.status === 'active';
			const pytorchOk = getIntegration('pytorch')?.status === 'active';
			const ollamaOk = getIntegration('ollama')?.status === 'active';

			const html = \`
				<!-- System Health -->
				<div class="card">
					<div class="card-title">
						<span class="icon">🖥️</span>
						System Health
					</div>
					<div class="card-content">
						<div class="status-row">
							<span class="status-label">Python</span>
							<span class="status-badge \${pythonOk ? 'ok' : 'error'}">\${pythonOk ? 'OK' : 'ERROR'}</span>
							<span class="status-detail">\${status.python?.version || 'N/A'}</span>
						</div>
						<div class="status-row">
							<span class="status-label">Virtual Env</span>
							<span class="status-badge \${venvOk ? 'ok' : 'warn'}">\${venvOk ? 'OK' : 'MISSING'}</span>
						</div>
						<div class="status-row">
							<span class="status-label">GPU</span>
							<span class="status-badge \${gpuOk ? 'ok' : 'warn'}">\${gpuOk ? 'OK' : 'N/A'}</span>
							<span class="status-detail">\${status.gpu?.count || 0} device(s)</span>
						</div>
						<div class="status-row">
							<span class="status-label">PyTorch</span>
							<span class="status-badge \${pytorchOk ? 'ok' : 'warn'}">\${pytorchOk ? 'OK' : 'N/A'}</span>
							<span class="status-detail">\${status.pytorch?.version || 'N/A'}</span>
						</div>
						<div class="status-row">
							<span class="status-label">Ollama</span>
							<span class="status-badge \${ollamaOk ? 'ok' : 'warn'}">\${ollamaOk ? 'OK' : 'N/A'}</span>
							<span class="status-detail">\${status.ollama?.model_count || 0} models</span>
						</div>
					</div>
				</div>

				<!-- System Metrics -->
				<div class="card">
					<div class="card-title">
						<span class="icon">📊</span>
						System Metrics
					</div>
					<div class="metric-grid">
						<div class="metric">
							<div class="metric-value">\${status.system?.cpu_count || 0}</div>
							<div class="metric-label">CPU Cores</div>
						</div>
						<div class="metric">
							<div class="metric-value">\${status.system?.cpu_percent?.toFixed(1) || 0}%</div>
							<div class="metric-label">CPU Usage</div>
						</div>
						<div class="metric">
							<div class="metric-value">\${(status.system?.memory_available_gb || 0).toFixed(1)}</div>
							<div class="metric-label">RAM Free (GB)</div>
						</div>
						<div class="metric">
							<div class="metric-value">\${(status.system?.disk_free_gb || 0).toFixed(0)}</div>
							<div class="metric-label">Disk Free (GB)</div>
						</div>
					</div>
				</div>

				<!-- GPU Info -->
				\${gpuOk && status.gpu?.gpus && status.gpu.gpus.length > 0 ? \`
					<div class="card">
						<div class="card-title">
							<span class="icon">⚡</span>
							GPU
						</div>
						\${status.gpu.gpus.map(gpu => \`
							<div class="gpu-item">
								<div class="gpu-name">\${gpu.name || 'Unknown GPU'}</div>
								<div class="gpu-memory">\${gpu.memory_total || 'N/A'} (\${gpu.memory_free || 'N/A'} free)</div>
								<div class="gpu-compute">Compute: \${gpu.compute_capability || 'N/A'}</div>
							</div>
						\`).join('')}
					</div>
				\` : ''}

				<!-- Actions -->
				<div class="card">
					<div class="card-title">
						<span class="icon">🎯</span>
						Quick Actions
					</div>
					<button class="btn btn-primary" data-action="startServer">🚀 Start Dashboard Server</button>
					<button class="btn" data-action="openBrowser">🌐 Open in Browser</button>
					<button class="btn" data-action="refresh">🔄 Refresh Status</button>
				</div>
			\`;

			content.innerHTML = html;
			document.getElementById('timestamp').textContent = \`Last updated: \${new Date(timestamp).toLocaleTimeString()}\`;
		}

		function refresh() {
			vscode.postMessage({ type: 'refresh' });
		}

		function startDashboard() {
			vscode.postMessage({ type: 'startServer' });
		}

		function openBrowser() {
			vscode.postMessage({ type: 'openBrowser' });
		}

		function handleCommandResult(result) {
			if (result.success) {
				console.log('Command succeeded:', result.stdout);
			} else {
				console.error('Command failed:', result.stderr);
			}
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
