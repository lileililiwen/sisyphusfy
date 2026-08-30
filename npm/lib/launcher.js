"use strict";

const os = require("os");
const path = require("path");
const https = require("https");
const { execFileSync } = require("child_process");
const fs = require("fs");
const crypto = require("crypto");

const REPOSITORY = "lileililiwen/sisyphusfy";
const VERSION = "0.1.0";

const PLATFORM_MAP = {
  linux: "linux",
  darwin: "darwin",
  win32: "win32",
};

const ARCH_MAP = {
  x64: "x86_64",
  arm64: "aarch64",
};

function getPlatform() {
  const platform = PLATFORM_MAP[process.platform];
  if (!platform) {
    throw new Error(
      `Unsupported platform: ${process.platform}. Supported: ${Object.keys(PLATFORM_MAP).join(", ")}`
    );
  }
  const arch = ARCH_MAP[process.arch];
  if (!arch) {
    throw new Error(
      `Unsupported architecture: ${process.arch}. Supported: ${Object.keys(ARCH_MAP).join(", ")}`
    );
  }
  return { platform, arch };
}

function getArtifactName(version, platform, arch) {
  return `sisyphusfy-${version}-${platform}-${arch}.tar.gz`;
}

function getDownloadUrl(version, filename) {
  return `https://github.com/${REPOSITORY}/releases/download/v${version}/${filename}`;
}

function download(url) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, { headers: { "User-Agent": "sisyphusfy-npm" } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        download(res.headers.location).then(resolve, reject);
        return;
      }
      if (res.statusCode !== 200) {
        reject(new Error(`Download failed: HTTP ${res.statusCode}`));
        return;
      }
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve(Buffer.concat(chunks)));
      res.on("error", reject);
    });
    request.on("error", reject);
  });
}

function verifyChecksum(data, expectedChecksum) {
  const actual = crypto.createHash("sha256").update(data).digest("hex");
  if (actual !== expectedChecksum) {
    throw new Error(
      `Checksum mismatch: expected ${expectedChecksum}, got ${actual}`
    );
  }
}

async function fetchChecksums(version) {
  const url = getDownloadUrl(version, "SHA256SUMS.txt");
  const data = await download(url);
  const text = data.toString("utf-8");
  const checksums = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const [hash, filename] = trimmed.split(/\s+/);
    if (hash && filename) {
      checksums[filename] = hash;
    }
  }
  return checksums;
}

function extractTarball(data, destDir) {
  const tarPath = path.join(destDir, "archive.tar.gz");
  fs.writeFileSync(tarPath, data);
  try {
    execFileSync("tar", ["xzf", tarPath, "-C", destDir], { stdio: "pipe" });
  } finally {
    try { fs.unlinkSync(tarPath); } catch {}
  }
}

function getInstallDir() {
  const home = os.homedir();
  return path.join(home, ".sisyphusfy", "bin");
}

function addToPath(dir) {
  const profile = process.platform === "win32"
    ? path.join(os.homedir(), "Documents", "PowerShell", "Microsoft.PowerShell_profile.ps1")
    : path.join(os.homedir(), ".bashrc");

  const pathEntry = process.platform === "win32"
    ? `$env:PATH = "${dir};$env:PATH"`
    : `export PATH="${dir}:$PATH"`;

  return { profile, pathEntry };
}

async function launch(args) {
  const installDir = getInstallDir();
  const executable = process.platform === "win32"
    ? path.join(installDir, "sisyphusfy.exe")
    : path.join(installDir, "sisyphusfy");

  if (fs.existsSync(executable)) {
    const child = execFileSync(executable, args, {
      stdio: "inherit",
      env: process.env,
    });
    process.exit(child.status || 0);
  }

  console.log("Sisyphusfy not found locally. Downloading...");

  const { platform, arch } = getPlatform();
  const filename = getArtifactName(VERSION, platform, arch);
  const checksums = await fetchChecksums(VERSION);
  const expectedChecksum = checksums[filename];

  if (!expectedChecksum) {
    throw new Error(
      `No checksum found for ${filename}. Available: ${Object.keys(checksums).join(", ")}`
    );
  }

  const data = await download(getDownloadUrl(VERSION, filename));
  verifyChecksum(data, expectedChecksum);

  fs.mkdirSync(installDir, { recursive: true });
  extractTarball(data, installDir);

  console.log(`Installed to ${installDir}`);

  const { profile, pathEntry } = addToPath(installDir);
  console.log(`\nAdd to your PATH:\n  ${pathEntry}`);
  console.log(`Or add to ${profile}`);

  const child = execFileSync(executable, args, {
    stdio: "inherit",
    env: process.env,
  });
  process.exit(child.status || 0);
}

module.exports = { launch, getPlatform, getArtifactName, getDownloadUrl };
