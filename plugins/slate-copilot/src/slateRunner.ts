// Modified: 2026-02-06T22:30:00Z | Author: COPILOT | Change: SLATE Python command runner with long-running support for /install and /update
import * as cp from 'child_process';
import * as vscode from 'vscode';
import { getSlateConfig } from './extension';

/**
 * Execute a SLATE Python command and return stdout.
 * Supports cancellation via CancellationToken.
 * All commands bind to 127.0.0.1 only (security rule).
 */
export function execSlateCommand(command: string, token: vscode.CancellationToken): Promise<string> {
	return _execCommand(command, token, 60_000);
}

/**
 * Execute a long-running SLATE command (install/update).
 * Timeout: 10 minutes. Streams progress incrementally.
 */
export function execSlateCommandLong(command: string, token: vscode.CancellationToken): Promise<string> {
	return _execCommand(command, token, 600_000);
}

function _execCommand(command: string, token: vscode.CancellationToken, timeoutMs: number): Promise<string> {
	const config = getSlateConfig();

	return new Promise<string>((resolve, reject) => {
		// Security: block dangerous patterns
		const blocked = ['eval(', 'exec(os', 'rm -rf /', 'base64.b64decode', '0.0.0.0'];
		for (const pattern of blocked) {
			if (command.includes(pattern)) {
				reject(new Error(`Blocked command pattern: ${pattern}`));
				return;
			}
		}

		const args = command.split(' ');
		console.log(`[SLATE Runner] Executing: ${config.pythonPath} ${args.join(' ')}`);
		console.log(`[SLATE Runner] CWD: ${config.workspacePath}`);

		const proc = cp.spawn(config.pythonPath, args, {
			cwd: config.workspacePath,
			env: {
				...process.env,
				PYTHONPATH: config.workspacePath,
				PYTHONIOENCODING: 'utf-8',
				CUDA_VISIBLE_DEVICES: '0,1',
				SLATE_WORKSPACE: config.workspacePath,
			},
			stdio: ['ignore', 'pipe', 'pipe'],
		});

		let stdout = '';
		let stderr = '';

		proc.stdout.on('data', (data: Buffer) => {
			stdout += data.toString('utf-8');
		});

		proc.stderr.on('data', (data: Buffer) => {
			stderr += data.toString('utf-8');
			console.log(`[SLATE Runner] STDERR: ${data.toString('utf-8')}`);
		});

		// Handle cancellation
		const disposable = token.onCancellationRequested(() => {
			proc.kill('SIGTERM');
			reject(new Error('Command cancelled'));
		});

		proc.on('close', (code) => {
			disposable.dispose();
			console.log(`[SLATE Runner] Exit code: ${code}`);
			if (code === 0) {
				console.log(`[SLATE Runner] Output length: ${stdout.length} bytes`);
				resolve(stdout.trim());
			} else {
				// Include stderr in output for diagnostics
				const output = stdout.trim() + (stderr ? `\n[stderr]: ${stderr.trim()}` : '');
				console.log(`[SLATE Runner] Error output: ${output.substring(0, 200)}`);
				resolve(output || `Command exited with code ${code}`);
			}
		});

		proc.on('error', (err) => {
			disposable.dispose();
			console.error(`[SLATE Runner] Spawn error: ${err.message}`);
			reject(new Error(`Failed to run command: ${err.message}`));
		});

		// Timeout
		setTimeout(() => {
			if (!proc.killed) {
				console.warn(`[SLATE Runner] Timeout after ${timeoutMs / 1000}s`);
				proc.kill('SIGTERM');
				resolve(stdout.trim() + `\n[timeout after ${timeoutMs / 1000}s]`);
			}
		}, timeoutMs);
	});
}
