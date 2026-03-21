<div align="center">

<picture>
  <source srcset="https://fonts.gstatic.com/s/e/notoemoji/latest/1f41f/512.webp" type="image/webp">
  <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f41f/512.gif" alt="🐟" width="100" height="100">
</picture>

# Tuna OS

### *Cloud-Native Enterprise Linux Desktop*

*Bootc-based immutable OS images built on AlmaLinux, CentOS Stream, and Fedora*

[![tunaOS](https://img.shields.io/github/stars/tuna-os/tunaOS?style=flat-square&label=⭐%20tunaOS&color=3b82f6)](https://github.com/tuna-os/tunaOS)
[![License](https://img.shields.io/github/license/tuna-os/tunaOS?style=flat-square&color=22c55e)](https://github.com/tuna-os/tunaOS/blob/main/LICENSE)
[![Website](https://img.shields.io/badge/tunaos.org-website-6366f1?style=flat-square)](https://tunaos.org)

</div>

---

Tuna OS brings a **modern cloud-native desktop** to Enterprise Linux. We take the stability of AlmaLinux and CentOS Stream and layer on the latest GNOME, KDE Plasma, COSMIC, and Niri desktops — shipped as immutable [bootc](https://containers.github.io/bootc/) container images.

Inspired by [Bluefin](https://projectbluefin.io) and the [Universal Blue](https://universal-blue.org/) community.

## Images

| Image | Base | Description |
|---|---|---|
| [**yellowfin**](https://github.com/tuna-os/tunaOS) | AlmaLinux Kitten 10 | Closest to upstream CentOS Stream |
| [**albacore**](https://github.com/tuna-os/tunaOS) | AlmaLinux 10 | Stable Enterprise Linux base |
| [**skipjack**](https://github.com/tuna-os/tunaOS) | CentOS Stream 10 | Experimental upstream builds |
| [**bonito-x13s**](https://github.com/tuna-os/bonito-x13s) | Fedora | Lenovo ThinkPad X13s (ARM64/Qualcomm) |

### Desktop & Hardware Options

Every image ships multiple desktops (`gnome`, `kde`, `cosmic`, `niri`) and hardware variants (`-hwe` for newer kernels, `-gdx` for NVIDIA/CUDA).

```
ghcr.io/tuna-os/yellowfin:gnome
ghcr.io/tuna-os/albacore:kde-gdx
ghcr.io/tuna-os/skipjack:gnome-hwe
```

## Key Repositories

| Repo | Purpose |
|---|---|
| [tunaOS](https://github.com/tuna-os/tunaOS) | Main image builder |
| [docs](https://github.com/tuna-os/docs) | Documentation site |
| [chunkah](https://github.com/tuna-os/chunkah) | OCI layer optimization tool |
| [github-copr](https://github.com/tuna-os/github-copr) | RPM build system with GitHub Actions |
| [bonito-x13s](https://github.com/tuna-os/bonito-x13s) | ThinkPad X13s ARM64 image |

---

<div align="center">

Built with ❤️ on Enterprise Linux · [tunaos.org](https://tunaos.org) · [Docs](https://github.com/tuna-os/docs)

</div>
