// Query the installed Codex app-server; no model calls or global configuration edits.
import { spawn } from 'node:child_process';
import { readdirSync } from 'node:fs';
import { resolve } from 'node:path';
const executable = process.argv[2];
if (!executable) throw new Error('Pass the absolute Codex executable path');
const cwd = process.cwd();
const expected = readdirSync(resolve(cwd, '.agents/skills'));
const child = spawn(executable, ['app-server', '--stdio'], { cwd, windowsHide: true });
let buffer = '';
const timeout = setTimeout(() => { child.kill(); process.exitCode = 1; console.error('Discovery timed out'); }, 30000);
function send(message) { child.stdin.write(JSON.stringify(message) + '\n'); }
child.stdout.on('data', data => {
  buffer += data;
  let index;
  while ((index = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, index); buffer = buffer.slice(index + 1);
    let message; try { message = JSON.parse(line); } catch { continue; }
    if (message.id === 1) {
      send({ method: 'initialized', params: {} });
      send({ id: 2, method: 'skills/list', params: { cwds: [cwd], forceReload: true } });
    }
    if (message.id === 2) {
      const entries = message.result?.data ?? [];
      const skills = entries.flatMap(entry => entry.skills ?? []);
      const found = skills.filter(skill => expected.includes(skill.name) && skill.enabled !== false && skill.path.replaceAll('\\', '/').includes('/.agents/skills/'));
      console.log(JSON.stringify({ expected: expected.length, discovered: found.map(({ name, path, scope }) => ({ name, path, scope })), errors: entries.flatMap(entry => entry.errors ?? []), rpcError: message.error }, null, 2));
      process.exitCode = found.length === expected.length ? 0 : 1;
      clearTimeout(timeout); child.kill();
    }
  }
});
child.on('error', error => { clearTimeout(timeout); console.error(error.message); process.exitCode = 1; });
send({ id: 1, method: 'initialize', params: { clientInfo: { name: 'deliverygap-skill-verification', version: '1.0.0' }, capabilities: { experimentalApi: true } } });
