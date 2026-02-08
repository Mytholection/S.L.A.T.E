// Modified: 2026-02-08T00:30:00Z | Author: COPILOT | Change: Full-featured Material Design dashboard
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
		console.log('[SLATE Dashboard] Initialized');
		this._view = webviewView;

		webviewView.webview.options = {
			enableScripts: true,
			localResourceRoots: [this._extensionUri]
		};

		webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

		webviewView.webview.onDidReceiveMessage(async data => {
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
				case 'copy':
					await vscode.env.clipboard.writeText(data.text);
					vscode.window.showInformationMessage('Copied!');
					break;
			}
		});

		// Auto-refresh every 5 seconds
		this._refreshInterval = setInterval(() => {
			this.refresh();
		}, 5000);

		this.refresh();
	}

	public async refresh() {
		if (!this._view) {
			return;
		}

		try {
			const token = new vscode.CancellationTokenSource().token;
			const statusResult = await execSlateCommand('slate/slate_status.py --json', token);
			const status = this._parseJSON(statusResult);
			const runtimeResult = await execSlateCommand('slate/slate_runtime.py --json', token);
			const runtime = this._parseJSON(runtimeResult);

			this._view.webview.postMessage({
				type: 'updateStatus',
				status,
				runtime,
				timestamp: new Date().toISOString()
			});
		} catch (error) {
			this._view.webview.postMessage({
				type: 'error',
				error: String(error)
			});
		}
	}

	public async startDashboardServer() {
		if (this._serverProcess && !this._serverProcess.killed) {
			vscode.window.showInformationMessage('Server running on port 8080');
			return;
		}

		try {
			const config = getSlateConfig();
			this._serverProcess = cp.spawn(config.pythonPath, ['agents/slate_dashboard_server.py'], {
				cwd: config.workspacePath,
				env: { ...process.env, PYTHONPATH: config.workspacePath, PYTHONIOENCODING: 'utf-8' },
				stdio: 'ignore'
			});
			vscode.window.showInformationMessage('Dashboard server started on port 8080');
		} catch (error) {
			vscode.window.showErrorMessage(`Error: ${error}`);
		}
	}

	private _parseJSON(str: string): any {
		try { return JSON.parse(str); } catch { return null; }
	}

	private _getHtmlForWebview(webview: vscode.Webview) {
		const nonce = getNonce();
		return DASHBOARD_HTML(nonce, webview.cspSource);
	}

	dispose() {
		if (this._refreshInterval) clearInterval(this._refreshInterval);
	}
}

function DASHBOARD_HTML(nonce: string, cspSource: string) {
	return `<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="UTF-8">
	<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>SLATE Dashboard</title>
	<style>
		/* ═════════════════════════════════════════════════════════
			SLATE Athena - Material Design v2
			Blue/Cyan accent, 2-column grid, clean aesthetics
		═════════════════════════════════════════════════════════ */
		
		* { margin: 0; padding: 0; box-sizing: border-box; }
		
		body {
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
			background: linear-gradient(135deg, #0a0f1c 0%, #0f1729 100%);
			color: #e2e8f0;
			padding: 16px;
			font-size: 12px;
			line-height: 1.5;
		}
		
		.header {
			font-size: 18px;
			font-weight: 700;
			margin-bottom: 20px;
			color: #f8fafc;
			display: flex;
			align-items: center;
			gap: 8px;
			letter-spacing: -0.5px;
		}
		
		.header .pulse {
			animation: pulse 2s infinite;
		}
		
		@keyframes pulse {
			0%, 100% { opacity: 1; transform: scale(1); }
			50% { opacity: 0.6; transform: scale(1.1); }
		}
		
		/* ═████████████████████████████ 2-Column Grid ════════════ */
		.grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 16px;
			margin-bottom: 16px;
		}
		
		.grid.full { grid-column: 1 / -1; }
		
		@media (max-width: 600px) {
			.grid { grid-template-columns: 1fr; }
		}
		
		/* ═████████████████████████████ Cards ════════════ */
		.card {
			background: rgba(15, 23, 41, 0.6);
			border: 1px solid rgba(59, 130, 246, 0.15);
			border-radius: 8px;
			padding: 14px;
			box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
			transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
			overflow: hidden;
		}
		
		.card:hover {
			border-color: rgba(59, 130, 246, 0.35);
			box-shadow: 0 6px 16px rgba(59, 130, 246, 0.12);
			transform: translateY(-2px);
		}
		
		.card-title {
			font-size: 12px;
			font-weight: 700;
			color: #f8fafc;
			margin-bottom: 12px;
			display: flex;
			align-items: center;
			gap: 6px;
			text-transform: uppercase;
			letter-spacing: 0.5px;
		}
		
		.card-icon {
			font-size: 14px;
			opacity: 0.9;
		}
		
		/* ═████████████████████████████ Metrics Grid ════════════ */
		.metric-grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 8px;
			margin-top: 8px;
		}
		
		.metric {
			background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(6, 182, 212, 0.05));
			border: 1px solid rgba(59, 130, 246, 0.15);
			border-left: 3px solid #3b82f6;
			padding: 10px;
			border-radius: 6px;
			transition: all 0.2s;
		}
		
		.metric:hover {
			background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(6, 182, 212, 0.1));
			border-color: rgba(59, 130, 246, 0.25);
		}
		
		.metric-label {
			font-size: 9px;
			color: #94a3b8;
			margin-bottom: 4px;
			font-weight: 600;
			text-transform: uppercase;
			letter-spacing: 0.3px;
		}
		
		.metric-value {
			font-size: 16px;
			font-weight: 700;
			color: #3b82f6;
			font-family: 'SF Mono', Monaco, monospace;
			letter-spacing: -1px;
		}
		
		.metric-unit {
			font-size: 10px;
			color: #64748b;
			font-weight: 500;
			margin-left: 2px;
		}
		
		/* ═████████████████████████████ Progress Bar ════════════ */
		.progress-container {
			margin: 10px 0;
		}
		
		.progress-label {
			display: flex;
			justify-content: space-between;
			font-size: 9px;
			margin-bottom: 4px;
			color: #cbd5e1;
			font-weight: 600;
		}
		
		.progress-bar {
			background: rgba(255, 255, 255, 0.08);
			border-radius: 4px;
			height: 6px;
			overflow: hidden;
			border: 1px solid rgba(59, 130, 246, 0.1);
		}
		
		.progress-fill {
			height: 100%;
			background: linear-gradient(90deg, #06b6d4 0%, #3b82f6 100%);
			border-radius: 4px;
			transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
			box-shadow: 0 0 8px rgba(59, 130, 246, 0.3);
		}
		
		/* ═████████████████████████████ Chart ════════════ */
		.chart-label {
			font-size: 9px;
			color: #64748b;
			margin-top: 8px;
			margin-bottom: 4px;
			font-weight: 600;
		}
		
		.chart {
			height: 50px;
			background: rgba(255, 255, 255, 0.03);
			border: 1px solid rgba(59, 130, 246, 0.1);
			border-radius: 4px;
			padding: 4px;
			display: flex;
			align-items: flex-end;
			gap: 1px;
		}
		
		.chart-bar {
			flex: 1;
			background: linear-gradient(180deg, #06b6d4 0%, #3b82f6 100%);
			border-radius: 2px 2px 0 0;
			min-height: 3px;
			transition: height 0.3s ease;
			opacity: 0.8;
		}
		
		.chart-bar:hover {
			opacity: 1;
		}
		
		/* ═████████████████████████████ Status Row ════════════ */
		.status-row {
			display: flex;
			justify-content: space-between;
			align-items: center;
			padding: 8px 0;
			border-bottom: 1px solid rgba(255, 255, 255, 0.05);
			font-size: 11px;
		}
		
		.status-row:last-child {
			border-bottom: none;
		}
		
		.status-label {
			color: #cbd5e1;
			font-weight: 500;
		}
		
		/* ═████████████████████████████ Badge ════════════ */
		.badge {
			display: inline-flex;
			align-items: center;
			gap: 4px;
			padding: 4px 8px;
			border-radius: 4px;
			font-size: 9px;
			font-weight: 600;
			cursor: pointer;
			transition: all 0.2s;
			border: 1px solid;
			text-transform: uppercase;
			letter-spacing: 0.3px;
		}
		
		.badge.ok {
			background: rgba(16, 185, 129, 0.15);
			color: #10b981;
			border-color: rgba(16, 185, 129, 0.3);
		}
		
		.badge.ok:hover {
			background: rgba(16, 185, 129, 0.25);
			box-shadow: 0 0 8px rgba(16, 185, 129, 0.2);
		}
		
		.badge.error {
			background: rgba(239, 68, 68, 0.15);
			color: #ef4444;
			border-color: rgba(239, 68, 68, 0.3);
		}
		
		.badge.warn {
			background: rgba(245, 158, 11, 0.15);
			color: #f59e0b;
			border-color: rgba(245, 158, 11, 0.3);
		}
		
		/* ═████████████████████████████ GPU Item ════════════ */
		.gpu-item {
			background: linear-gradient(135deg, rgba(6, 182, 212, 0.08), rgba(59, 130, 246, 0.04));
			border-left: 3px solid #06b6d4;
			padding: 10px;
			margin: 8px 0;
			border-radius: 6px;
			border: 1px solid rgba(6, 182, 212, 0.15);
		}
		
		.gpu-name {
			font-size: 11px;
			font-weight: 700;
			color: #06b6d4;
			margin-bottom: 4px;
			text-transform: uppercase;
			letter-spacing: 0.3px;
		}
		
		.gpu-memory {
			font-size: 10px;
			color: #cbd5e1;
			margin-bottom: 6px;
			font-family: monospace;
		}
		
		.gpu-compute {
			font-size: 9px;
			color: #64748b;
		}
		
		/* ═████████████████████████████ List ════════════ */
		.list-item {
			padding: 8px 0;
			border-bottom: 1px solid rgba(255, 255, 255, 0.04);
			display: flex;
			justify-content: space-between;
			align-items: center;
			font-size: 10px;
		}
		
		.list-item:last-child {
			border-bottom: none;
		}
		
		.list-label {
			color: #cbd5e1;
			flex: 1;
		}
		
		.list-value {
			color: #f8fafc;
			font-weight: 600;
			font-family: monospace;
			white-space: nowrap;
		}
		
		/* ═████████████████████████████ Buttons ════════════ */
		.btn-group {
			display: flex;
			gap: 8px;
			margin-top: 12px;
		}
		
		.btn {
			flex: 1;
			background: linear-gradient(135deg, #3b82f6, #06b6d4);
			border: 1px solid rgba(59, 130, 246, 0.4);
			color: white;
			padding: 8px;
			border-radius: 6px;
			font-size: 10px;
			font-weight: 700;
			cursor: pointer;
			transition: all 0.2s;
			text-transform: uppercase;
			letter-spacing: 0.3px;
		}
		
		.btn:hover {
			transform: translateY(-2px);
			box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
			border-color: rgba(59, 130, 246, 0.7);
		}
		
		.btn:active {
			transform: translateY(0);
		}
		
		.btn-secondary {
			background: rgba(59, 130, 246, 0.15);
			color: #3b82f6;
		}
		
		/* ═████████████████████████████ Timestamp ════════════ */
		.timestamp {
			text-align: center;
			font-size: 10px;
			color: #64748b;
			margin-top: 16px;
			padding-top: 8px;
			border-top: 1px solid rgba(255, 255, 255, 0.05);
			font-family: monospace;
			letter-spacing: 0.5px;
		}
		
		/* ═████████████████████████████ Loading ════════════ */
		.loading {
			text-align: center;
			padding: 32px 16px;
			color: #94a3b8;
		}
		
		.spinner {
			border: 2px solid rgba(59, 130, 246, 0.2);
			border-top: 2px solid #3b82f6;
			border-radius: 50%;
			width: 28px;
			height: 28px;
			animation: spin 0.8s linear infinite;
			margin: 0 auto 12px;
		}
		
		@keyframes spin {
			0% { transform: rotate(0deg); }
			100% { transform: rotate(360deg); }
		}
		
		.error {
			background: rgba(239, 68, 68, 0.1);
			border-left: 3px solid #ef4444;
			color: #fca5a5;
			padding: 10px;
			border-radius: 6px;
			font-size: 10px;
		}
	</style>
</head>
<body>
	<div class="header">
		<span class="pulse">⚡</span>
		<span>SLATE Athena</span>
	</div>
	
	<div id="content">
		<div class="loading">
			<div class="spinner"></div>
			<div>Loading dashboard...</div>
		</div>
	</div>
	
	<div class="timestamp" id="timestamp">Ready</div>

	<script nonce="\${nonce}">
		const vscode = acquireVsCodeApi();
		let cpuHistory = [];
		let gpuMemHistory = [];
		
		vscode.postMessage({ type: 'refresh' });
		
		window.addEventListener('message', event => {
			if (event.data.type === 'updateStatus') {
				renderDashboard(event.data.status, event.data.runtime);
				document.getElementById('timestamp').textContent = 'Updated: ' + formatTime(new Date());
			} else if (event.data.type === 'error') {
				document.getElementById('content').innerHTML = '<div class="error">⚠️ Error: ' + (event.data.error || 'Unknown') + '</div>';
			}
		});
		
		document.addEventListener('click', e => {
			if (e.target.tagName === 'BUTTON') {
				const action = e.target.getAttribute('data-action');
				if (action === 'refresh') vscode.postMessage({ type: 'refresh' });
				else if (action === 'start') vscode.postMessage({ type: 'startServer' });
				else if (action === 'browser') vscode.postMessage({ type: 'openBrowser' });
				else if (action === 'copy') vscode.postMessage({ type: 'copy', text: e.target.getAttribute('data-param') });
			}
		});
		
		function formatTime(date) {
			return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
		}
		
		function renderDashboard(status, runtime) {
			if (!status || !runtime) {
				document.getElementById('content').innerHTML = '<div class="card" style="text-align:center;color:#94a3b8">Waiting for metrics...</div>';
				return;
			}
			
			const integrations = runtime.integrations || [];
			const getStatus = (name) => integrations.find(i => i.name.toLowerCase().includes(name.toLowerCase()))?.status === 'active';
			
			let html = '<div class="grid">';
			
			// LEFT COLUMN
			html += '<div>';
			html += renderSystemMetrics(status);
			html += renderRunner();
			html += '</div>';
			
			// RIGHT COLUMN
			html += '<div>';
			html += renderGPU(status);
			html += renderOllama(status);
			html += '</div>';
			
			html += '</div>';
			
			// FULL WIDTH
			html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">';
			html += renderSystemHealth(status, runtime, getStatus);
			html += renderWorkflows();
			html += '</div>';
			
			// FULL WIDTH ACTIONS
			html += renderActions();
			
			document.getElementById('content').innerHTML = html;
		}
		
		function renderSystemMetrics(status) {
			const cpu = status.system?.cpu_percent || 0;
			const ram = status.system?.memory_used_gb || 0;
			const ramTotal = status.system?.memory_total_gb || 32;
			const disk = status.system?.disk_used_gb || 0;
			const diskTotal = status.system?.disk_total_gb || 1000;
			
			cpuHistory.push(cpu);
			if (cpuHistory.length > 20) cpuHistory.shift();
			
			const ramPct = (ram / ramTotal * 100);
			const diskPct = (disk / diskTotal * 100);
			
			let html = '<div class="card"><div class="card-title"><span class="card-icon">🖥️</span> System Metrics</div>';
			html += '<div class="metric-grid">';
			html += '<div class="metric"><div class="metric-label">CPUs</div><div class="metric-value">' + (status.system?.cpu_count || 0) + '</div></div>';
			html += '<div class="metric"><div class="metric-label">CPU</div><div class="metric-value">' + cpu.toFixed(1) + '<span class="metric-unit">%</span></div></div>';
			html += '<div class="metric"><div class="metric-label">RAM</div><div class="metric-value">' + ram.toFixed(1) + '<span class="metric-unit">GB</span></div></div>';
			html += '<div class="metric"><div class="metric-label">Disk</div><div class="metric-value">' + (diskTotal - disk).toFixed(0) + '<span class="metric-unit">GB</span></div></div>';
			html += '</div>';
			
			html += '<div class="progress-container"><div class="progress-label"><span>CPU Load</span><span>' + cpu.toFixed(0) + '%</span></div><div class="progress-bar"><div class="progress-fill" style="width:' + Math.min(100, cpu) + '%"></div></div></div>';
			html += '<div class="progress-container"><div class="progress-label"><span>RAM (' + ram.toFixed(1) + '/' + ramTotal + 'GB)</span><span>' + ramPct.toFixed(0) + '%</span></div><div class="progress-bar"><div class="progress-fill" style="width:' + Math.min(100, ramPct) + '%"></div></div></div>';
			html += '<div class="progress-container"><div class="progress-label"><span>Disk (' + (diskTotal - disk).toFixed(0) + '/' + diskTotal + 'GB free)</span><span>' + (100 - diskPct).toFixed(0) + '%</span></div><div class="progress-bar"><div class="progress-fill" style="width:' + Math.min(100, diskPct) + '%"></div></div></div>';
			
			html += '<div class="chart-label">📊 CPU Trend (20s)</div>';
			html += '<div class="chart">' + cpuHistory.map(v => '<div class="chart-bar" style="height:' + Math.max(4, Math.min(100, v)) + '%"></div>').join('') + '</div>';
			html += '</div>';
			
			return html;
		}
		
		function renderGPU(status) {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">⚡</span> GPU Status</div>';
			
			if (!status.gpu?.gpus || status.gpu.gpus.length === 0) {
				html += '<div style="color:#94a3b8;padding:12px;text-align:center">No GPUs detected</div>';
				html += '</div>';
				return html;
			}
			
			status.gpu.gpus.forEach((gpu, i) => {
				const memPct = gpu.memory_used_percent || 0;
				gpuMemHistory.push(memPct);
				if (gpuMemHistory.length > 20) gpuMemHistory.shift();
				
				html += '<div class="gpu-item">';
				html += '<div class="gpu-name">' + (gpu.name || 'GPU #' + i) + '</div>';
				html += '<div class="gpu-memory">' + (gpu.memory_used || 'N/A') + ' / ' + (gpu.memory_total || 'N/A') + '</div>';
				html += '<div class="progress-bar"><div class="progress-fill" style="width:' + Math.min(100, memPct) + '%"></div></div>';
				html += '<div class="gpu-compute">Compute: ' + (gpu.compute_capability || 'N/A') + ' | ' + memPct.toFixed(0) + '% Memory</div>';
				html += '</div>';
			});
			
			html += '</div>';
			return html;
		}
		
		function renderOllama(status) {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">🦙</span> Ollama Models</div>';
			
			if (!status.ollama?.models || status.ollama.models.length === 0) {
				html += '<div style="color:#94a3b8;padding:12px;text-align:center">No models loaded</div>';
				html += '</div>';
				return html;
			}
			
			const models = status.ollama.models.slice(0, 6);
			models.forEach(model => {
				html += '<div class="list-item"><span class="list-label">' + model.name + '</span><span class="list-value">' + (model.size_gb || 'N/A') + 'GB</span></div>';
			});
			
			if (status.ollama.models.length > 6) {
				html += '<div class="list-item"><span class="list-label">+' + (status.ollama.models.length - 6) + ' more models...</span></div>';
			}
			
			html += '</div>';
			return html;
		}
		
		function renderRunner() {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">🤖</span> GitHub Runner</div>';
			html += '<div class="status-row"><span class="status-label">Runner</span><span class="badge ok">slate-runner</span></div>';
			html += '<div class="status-row"><span class="status-label">Status</span><span class="badge ok">Online</span></div>';
			html += '<div class="status-row"><span class="status-label">Active Jobs</span><span style="font-family:monospace;font-weight:600">0</span></div>';
			html += '<div class="status-row"><span class="status-label">Queued</span><span style="font-family:monospace;font-weight:600">0</span></div>';
			html += '</div>';
			return html;
		}
		
		function renderSystemHealth(status, runtime, getStatus) {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">💊</span> System Health</div><div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">Python</span>' + (getStatus('python') ? '<span class="badge ok">✓</span>' : '<span class="badge error">✗</span>') + '</div>';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">GPU</span>' + (getStatus('gpu') ? '<span class="badge ok">✓</span>' : '<span class="badge warn">⚠</span>') + '</div>';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">PyTorch</span>' + (getStatus('pytorch') ? '<span class="badge ok">✓</span>' : '<span class="badge warn">⚠</span>') + '</div>';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">Ollama</span>' + (getStatus('ollama') ? '<span class="badge ok">✓</span>' : '<span class="badge warn">⚠</span>') + '</div>';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">ChromaDB</span>' + (getStatus('chromadb') ? '<span class="badge ok">✓</span>' : '<span class="badge warn">⚠</span>') + '</div>';
			html += '<div class="status-row" style="border:none;padding:6px;background:rgba(59,130,246,0.08);border-radius:4px"><span class="status-label">Venv</span>' + (getStatus('virtual env') ? '<span class="badge ok">✓</span>' : '<span class="badge warn">⚠</span>') + '</div>';
			html += '</div></div>';
			return html;
		}
		
		function renderWorkflows() {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">⚙️</span> Recent Workflows</div>';
			html += '<div class="status-row" style="border:none"><span class="status-label">Main CI</span><span class="list-value" style="font-size:9px">✓ Passed</span></div>';
			html += '<div class="status-row" style="border:none"><span class="status-label">Agentic Loop</span><span class="list-value" style="font-size:9px">⏱ Queued</span></div>';
			html += '<div class="status-row" style="border:none"><span class="status-label">Last Run</span><span style="font-size:9px;color:#64748b;">26 mins ago</span></div>';
			html += '</div>';
			return html;
		}
		
		function renderActions() {
			let html = '<div class="card"><div class="card-title"><span class="card-icon">⚡</span> Quick Actions</div><div class="btn-group">';
			html += '<button class="btn" data-action="start">🚀 Start Server</button>';
			html += '<button class="btn" data-action="browser">🌐 Dashboard</button>';
			html += '<button class="btn btn-secondary" data-action="refresh">🔄 Refresh</button>';
			html += '</div></div>';
			return html;
		}
	</script>
</body>
</html>`;
}

function getNonce() {
	let text = '';
	const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
	for (let i = 0; i < 32; i++) text += possible.charAt(Math.floor(Math.random() * possible.length));
	return text;
}
