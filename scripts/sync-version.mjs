// 版本同步：git tag 为唯一版本来源，落到 README.md / frontend/package.json / backend/VERSION
//
// 用法：
//   node scripts/sync-version.mjs            # 从最新 git tag 同步
//   node scripts/sync-version.mjs v0.3.0     # 同步到指定版本
//   node scripts/sync-version.mjs --print-only
//
// 发版流程（顺序执行，保证 tag 指向的文件内容已同步）：
//   node scripts/sync-version.mjs vX.Y.Z
//   git add -A && git commit -m "chore(release): vX.Y.Z"
//   git tag vX.Y.Z && git push && git push origin vX.Y.Z
import { execSync } from 'child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));
const ROOT = resolve(__dirname, '..');

function getVersion() {
  const arg = process.argv.slice(2).find((a) => /^v\d+\.\d+\.\d+$/.test(a));
  if (arg) return arg;
  try {
    return execSync('git describe --tags --abbrev=0', { cwd: ROOT, encoding: 'utf-8' }).trim();
  } catch {
    throw new Error('无法获取 git tag，请显式传版本参数：node scripts/sync-version.mjs vX.Y.Z');
  }
}

function updateReadme(version) {
  const path = resolve(ROOT, 'README.md');
  const content = readFileSync(path, 'utf-8');
  if (!/当前版本：v?\d+\.\d+\.\d+/.test(content)) {
    throw new Error('README.md 缺少「当前版本：vX.Y.Z」行，无法同步');
  }
  const next = content.replace(/当前版本：v?\d+\.\d+\.\d+/, `当前版本：${version}`);
  writeFileSync(path, next, 'utf-8');
  return next;
}

function updatePackageJson(version) {
  const path = resolve(ROOT, 'frontend', 'package.json');
  const content = readFileSync(path, 'utf-8');
  if (!/"version"\s*:\s*"[\d.]+"/.test(content)) {
    throw new Error('frontend/package.json 未找到 version 字段');
  }
  // 文本替换保留原有格式，避免 JSON 重排产生噪音 diff
  const next = content.replace(/("version"\s*:\s*")[\d.]+(")/, `$1${version.replace(/^v/, '')}$2`);
  writeFileSync(path, next, 'utf-8');
  return next;
}

function updateVersionFile(version) {
  writeFileSync(resolve(ROOT, 'backend', 'VERSION'), version.replace(/^v/, '') + '\n', 'utf-8');
}

function checkConsistency(version) {
  const plain = version.replace(/^v/, '');
  const readme = readFileSync(resolve(ROOT, 'README.md'), 'utf-8').match(/当前版本：v?(\d+\.\d+\.\d+)/)?.[1];
  const pkg = JSON.parse(readFileSync(resolve(ROOT, 'frontend', 'package.json'), 'utf-8')).version;
  const verFile = readFileSync(resolve(ROOT, 'backend', 'VERSION'), 'utf-8').trim();
  return {
    readmeOk: readme === plain,
    pkgOk: pkg === plain,
    versionFileOk: verFile === plain,
    found: { README: readme, 'package.json': pkg, VERSION: verFile },
  };
}

function main() {
  const version = getVersion();
  console.log(`[sync-version] 版本: ${version}`);
  updateReadme(version);
  console.log(`[sync-version] README.md 已同步 → ${version}`);
  updatePackageJson(version);
  console.log(`[sync-version] frontend/package.json 已同步 → ${version}`);
  updateVersionFile(version);
  console.log(`[sync-version] backend/VERSION 已同步 → ${version}`);

  const check = checkConsistency(version);
  if (!check.readmeOk || !check.pkgOk || !check.versionFileOk) {
    console.error('[sync-version] 一致性校验失败:', check.found);
    process.exit(1);
  }
  console.log('[sync-version] 四处版本一致: git tag / README.md / frontend/package.json / backend/VERSION');
}

if (process.argv.includes('--print-only')) {
  console.log(getVersion());
} else {
  main();
}
