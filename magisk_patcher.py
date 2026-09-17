#!/usr/bin/env python3
"""
magisk_patcher.py
=================
Standalone Magisk boot image patcher for Termux (arm64-v8a only).

Fetches the latest official Magisk release from GitHub, extracts arm64-v8a
binaries, patches a user-supplied boot.img, and saves the result as:

    /sdcard/Download/magisk_patched_boot.img

Usage:
    python magisk_patcher.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Theme (golden / amber)
# ---------------------------------------------------------------------------
GOLD = "\033[38;5;220m"
GOLD_DIM = "\033[38;5;178m"
AMBER = "\033[38;5;214m"
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
GITHUB_API = "https://api.github.com/repos/topjohnwu/Magisk/releases/latest"
USER_AGENT = "Termux-Magisk-Patcher/2.0"
TARGET_ABI = "arm64-v8a"
OUTPUT_PATH = Path("/sdcard/Download/magisk_patched_boot.img")


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def banner():
    print(CLEAR, end="")
    print(f"""
{GOLD}{BOLD}
    ╔══════════════════════════════════════════════════════════╗
    ║                                                          ║
    ║          ███╗   ███╗ █████╗  ██████╗ ██╗███████╗██╗  ██╗ ║
    ║          ████╗ ████║██╔══██╗██╔════╝ ██║██╔════╝██║ ██╔╝ ║
    ║          ██╔████╔██║███████║██║  ███╗██║███████╗█████╔╝  ║
    ║          ██║╚██╔╝██║██╔══██║██║   ██║██║╚════██║██╔═██╗  ║
    ║          ██║ ╚═╝ ██║██║  ██║╚██████╔╝██║███████║██║  ██╗ ║
    ║          ╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝ ║
    ║                                                          ║
    ║              Boot Image Patcher  ·  arm64-v8a            ║
    ║                                                          ║
    ╚══════════════════════════════════════════════════════════╝
{RESET}
{GOLD_DIM}  ────────────────────────────────────────────────────────────{RESET}
{AMBER}  Flashing a bad image can soft-brick your device. Be careful.{RESET}
{GOLD_DIM}  ────────────────────────────────────────────────────────────{RESET}
""")


def info(msg):
    print(f"{CYAN}[*] {msg}{RESET}")


def ok(msg):
    print(f"{GREEN}[+] {msg}{RESET}")


def warn(msg):
    print(f"{YELLOW}[!] {msg}{RESET}")


def fail(msg):
    print(f"{RED}[!] {msg}{RESET}")
    sys.exit(1)


def step(msg):
    print(f"\n{GOLD}{BOLD}→ {msg}{RESET}")


# ---------------------------------------------------------------------------
# Step 1 – Ask user for boot.img path
# ---------------------------------------------------------------------------
def ask_boot_path():
    print(f"""
{GOLD}{BOLD}  BOOT IMAGE{RESET}
{GOLD_DIM}  ──────────{RESET}
  Example: /sdcard/Download/boot.img
""")
    while True:
        raw = input(f"{GOLD}Enter full path to boot.img: {RESET}").strip()
        if not raw:
            warn("Path cannot be empty.")
            continue
        path = Path(os.path.expanduser(raw)).resolve()
        if not path.is_file():
            fail(f"File not found: {path}")
        size_mb = path.stat().st_size / (1024 * 1024)
        ok(f"Input: {path} ({size_mb:.1f} MB)")
        return path


# ---------------------------------------------------------------------------
# Step 2 – Fetch latest Magisk APK URL from GitHub
# ---------------------------------------------------------------------------
def get_latest_apk_url():
    step("Fetching latest Magisk release from GitHub")
    req = urllib.request.Request(
        GITHUB_API,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        fail(f"GitHub API error: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        fail(f"Network error: {e.reason}")
    except json.JSONDecodeError:
        fail("Invalid JSON from GitHub API")

    tag = data.get("tag_name", "unknown")
    apk_url = None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".apk") and "Magisk" in name and "debug" not in name.lower():
            apk_url = asset.get("browser_download_url")
            break
    if not apk_url:
        for asset in data.get("assets", []):
            if asset.get("name", "").endswith(".apk"):
                apk_url = asset.get("browser_download_url")
                break
    if not apk_url:
        fail("No APK found in the latest Magisk release")

    ok(f"Latest release: {tag}")
    info(f"Download URL: {apk_url}")
    return apk_url, tag


# ---------------------------------------------------------------------------
# Step 3 – Download the APK
# ---------------------------------------------------------------------------
def download(url, dest):
    info(f"Downloading {dest.name} …")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
            total = resp.headers.get("Content-Length")
            total = int(total) if total else None
            done = 0
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(
                        f"\r{CYAN}    {done/1024/1024:.1f} / {total/1024/1024:.1f} MB ({pct}%){RESET}",
                        end="",
                        flush=True,
                    )
            print()
    except Exception as e:
        fail(f"Download failed: {e}")
    ok(f"Saved → {dest.name}")


# ---------------------------------------------------------------------------
# Step 4 – Extract arm64-v8a binaries only
# ---------------------------------------------------------------------------
def extract_binaries(apk_path, work_dir):
    step(f"Extracting binaries for {TARGET_ABI} only")
    bin_dir = work_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    mapping = {
        f"lib/{TARGET_ABI}/libmagiskboot.so": bin_dir / "magiskboot",
        f"lib/{TARGET_ABI}/libmagiskinit.so": bin_dir / "magiskinit",
    }
    magisk_candidates = [
        f"lib/{TARGET_ABI}/libmagisk.so",
        f"lib/{TARGET_ABI}/libmagisk64.so",
    ]

    try:
        with zipfile.ZipFile(apk_path, "r") as zf:
            names = set(zf.namelist())

            for src, dst in mapping.items():
                if src not in names:
                    fail(f"Missing required file inside APK: {src}")
                with zf.open(src) as sf, open(dst, "wb") as df:
                    shutil.copyfileobj(sf, df)
                dst.chmod(0o755)
                ok(f"Extracted {dst.name}")

            for cand in magisk_candidates:
                if cand in names:
                    dst = bin_dir / "magisk"
                    with zf.open(cand) as sf, open(dst, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    dst.chmod(0o755)
                    ok(f"Extracted magisk ← {cand}")
                    break
            else:
                warn("magisk binary not found – continuing without it")

            if "assets/stub.apk" in names:
                dst = bin_dir / "stub.apk"
                with zf.open("assets/stub.apk") as sf, open(dst, "wb") as df:
                    shutil.copyfileobj(sf, df)
                ok("Extracted stub.apk")
            else:
                warn("stub.apk not found – continuing without it")

    except zipfile.BadZipFile:
        fail("Downloaded file is not a valid APK/ZIP")

    magiskboot = bin_dir / "magiskboot"
    if not magiskboot.is_file():
        fail("magiskboot was not extracted")
    return magiskboot, bin_dir


# ---------------------------------------------------------------------------
# Helper – run magiskboot
# ---------------------------------------------------------------------------
def run_boot(magiskboot, args, cwd):
    return subprocess.run(
        [str(magiskboot)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=180,
    )


# ---------------------------------------------------------------------------
# Step 5 – Patch the boot image
# ---------------------------------------------------------------------------
def patch(magiskboot, bin_dir, boot_img, output_img, work_dir):
    patch_dir = work_dir / "patch"
    patch_dir.mkdir(parents=True, exist_ok=True)

    stock = patch_dir / "stock_boot.img"
    shutil.copy2(boot_img, stock)

    # ----- Unpack -----
    step("Unpacking boot image")
    r = run_boot(magiskboot, ["unpack", str(stock)], patch_dir)
    if r.returncode not in (0, 2):
        if r.stderr:
            print(GRAY + r.stderr.strip() + RESET)
        fail("Failed to unpack boot image")
    if r.returncode == 2:
        warn("ChromeOS image detected – continuing")
    ok("Unpack complete")
    if r.stdout.strip():
        for line in r.stdout.strip().splitlines():
            print(f"    {GRAY}{line}{RESET}")

    ramdisk = patch_dir / "ramdisk.cpio"
    kernel = patch_dir / "kernel"

    # ----- Compress extras -----
    step("Preparing Magisk files for injection")

    def compress(src_name, out_name):
        src = bin_dir / src_name
        if not src.is_file():
            return False
        dst = patch_dir / out_name
        r = run_boot(magiskboot, ["compress=xz", str(src), str(dst)], patch_dir)
        if r.returncode != 0:
            warn(f"Could not compress {src_name}")
            return False
        ok(f"Compressed {src_name} → {out_name}")
        return True

    has_magisk = compress("magisk", "magisk.xz")
    has_stub = compress("stub.apk", "stub.xz")

    magiskinit = bin_dir / "magiskinit"
    if not magiskinit.is_file():
        fail("magiskinit is missing – cannot patch")
    shutil.copy2(magiskinit, patch_dir / "magiskinit")

    # ----- Patch ramdisk -----
    if ramdisk.is_file():
        step("Injecting Magisk into ramdisk")
        cmds = [
            "add 0750 init magiskinit",
            "mkdir 0750 overlay.d",
            "mkdir 0750 overlay.d/sbin",
        ]
        if has_magisk:
            cmds.append("add 0644 overlay.d/sbin/magisk.xz magisk.xz")
        if has_stub:
            cmds.append("add 0644 overlay.d/sbin/stub.xz stub.xz")

        (patch_dir / "config").write_text(
            "KEEPVERITY=false\nKEEPFORCEENCRYPT=false\nRECOVERYMODE=false\n"
        )
        cmds.append("mkdir 000 .backup")
        cmds.append("add 000 .backup/.magisk config")

        r = run_boot(magiskboot, ["cpio", "ramdisk.cpio"] + cmds, patch_dir)
        if r.returncode != 0:
            if r.stderr:
                print(GRAY + r.stderr.strip() + RESET)
            fail("Failed to patch ramdisk")
        ok("Ramdisk patched")
    else:
        warn("No ramdisk.cpio found – skipping ramdisk injection")

    # ----- Kernel hexpatch (optional) -----
    if kernel.is_file():
        step("Checking kernel for skip_initramfs")
        r = run_boot(
            magiskboot,
            [
                "hexpatch",
                "kernel",
                "736B69705F696E697472616D6673",  # skip_initramfs
                "77616E745F696E697472616D6673",  # want_initramfs
            ],
            patch_dir,
        )
        if r.returncode == 0:
            ok("Kernel hex-patched")
        else:
            info("No skip_initramfs pattern found (OK)")

    # ----- Repack -----
    step("Repacking boot image")
    r = run_boot(magiskboot, ["repack", str(stock)], patch_dir)
    if r.returncode != 0:
        if r.stderr:
            print(GRAY + r.stderr.strip() + RESET)
        fail("Failed to repack boot image")

    new_boot = patch_dir / "new-boot.img"
    if not new_boot.is_file():
        fail("new-boot.img was not created")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(new_boot, output_img)
    ok(f"Patched image saved → {output_img}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    banner()
    info(f"Architecture : {TARGET_ABI} (strict)")
    info(f"Output file  : {OUTPUT_PATH}")

    boot_path = ask_boot_path()

    work_dir = Path(tempfile.mkdtemp(prefix="magisk_patch_"))
    info(f"Temp directory: {work_dir}")

    try:
        apk_url, tag = get_latest_apk_url()
        apk_path = work_dir / f"Magisk-{tag}.apk"
        download(apk_url, apk_path)

        magiskboot, bin_dir = extract_binaries(apk_path, work_dir)

        patch(
            magiskboot=magiskboot,
            bin_dir=bin_dir,
            boot_img=boot_path,
            output_img=OUTPUT_PATH,
            work_dir=work_dir,
        )

        print(f"""
{GOLD}{BOLD}══════════════════════════════════════════════════════════{RESET}
{GREEN}  Done!{RESET}

  Patched boot image:
    {OUTPUT_PATH}

  Typical next steps:
    1. Reboot to fastboot
    2. fastboot flash boot magisk_patched_boot.img
    3. Reboot and open the Magisk app

{AMBER}  Keep a backup of your original boot.img!{RESET}
{GOLD}{BOLD}══════════════════════════════════════════════════════════{RESET}
""")
    except KeyboardInterrupt:
        print(f"\n{GRAY}Cancelled.{RESET}")
        sys.exit(130)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        info("Temporary files removed.")


if __name__ == "__main__":
    main()
