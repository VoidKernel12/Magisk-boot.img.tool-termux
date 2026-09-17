# Magisk Boot Patcher (Termux)

Simple tool to patch an Android `boot.img` with the latest official Magisk, entirely from Termux.

**Credit:** Magisk by [topjohnwu](https://github.com/topjohnwu/Magisk) (John Wu)

- Architecture: **arm64-v8a only**
- Output: `/sdcard/Download/magisk_patched_boot.img`

---

## Install

```bash
pkg install git python -y
```
```bashb
git clone https://github.com/VoidKernel12/Magisk-boot.img.tool-termux.git
```
```bash
cd Magisk-boot.img.tool-termux
```
```bash
bash install.sh
```

---

## Usage

```bash
python magisk_patcher.py
```

Enter the path to your stock boot image, for example:

```
/sdcard/Download/boot.img
```

After patching, the file will be saved at:

```
/sdcard/Download/magisk_patched_boot.img
```

---

## Flash commands

```bash
fastboot flash boot /sdcard/Download/magisk_patched_boot.img
fastboot reboot
```

On some devices:

```bash
fastboot flash init_boot /sdcard/Download/magisk_patched_boot.img
fastboot reboot
```

---

## Warning

Flashing a wrong image can soft-brick your device.  
Always keep a backup of the original `boot.img`.  
You assume all risk.

Magisk © topjohnwu — this tool only uses the official Magisk binaries.
