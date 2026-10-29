import assert from 'node:assert/strict';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { resolve, dirname, extname } from 'node:path';
const root = resolve(import.meta.dirname, '..');
const read = path => readFileSync(resolve(root, path), 'utf8');
const packageJson = JSON.parse(read('frontend/package.json'));
assert(packageJson.scripts.build.includes('tsc'));
JSON.parse(read('frontend/tsconfig.json'));
const manifest = JSON.parse(read('frontend/public/manifest.webmanifest'));
for (const icon of manifest.icons) {
  const data = readFileSync(resolve(root, 'frontend/public', icon.src.slice(1)));
  assert.equal(data.subarray(1, 4).toString(), 'PNG');
  assert.equal(`${data.readUInt32BE(16)}x${data.readUInt32BE(20)}`, icon.sizes);
}
function checkImports(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) { checkImports(path); continue; }
    if (!['.ts', '.tsx'].includes(extname(path))) continue;
    const source = readFileSync(path, 'utf8');
    assert(!source.includes('\uFFFD'), `Invalid UTF-8: ${path}`);
    for (const match of source.matchAll(/(?:from\s+|import\s*)['"](\.\.?\/[^'"]+)['"]/g)) {
      const target = resolve(dirname(path), match[1]);
      assert(['', '.ts', '.tsx', '.css'].some(extension => existsSync(target + extension)), `Missing import ${target}`);
    }
  }
}
checkImports(resolve(root, 'frontend/src'));
for (const path of ['compose.yaml', 'infra/Caddyfile', 'backend/app/main.py', 'backend/migrations/versions/0001_initial.py', '.env.example', 'README.md']) assert(existsSync(resolve(root, path)), `Missing ${path}`);
console.log('Structure check passed: JSON, local TS imports, PWA icons and required configuration. This is not a build or runtime test.');
