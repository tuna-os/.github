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

Tuna OS brings a **modern cloud-native desktop** to Enterprise Linux and
community distributions. Images combine an immutable
[bootc](https://containers.github.io/bootc/) base with the desktop and hardware
options supported by each distribution.

Inspired by [Bluefin](https://projectbluefin.io) and the [Universal Blue](https://universal-blue.org/) community.

## Featured Enterprise Linux images

| Image | Base | Description |
|---|---|---|
| [**yellowfin**](https://github.com/tuna-os/tunaOS) | AlmaLinux Kitten 10 | Closest to upstream CentOS Stream |
| [**albacore**](https://github.com/tuna-os/tunaOS) | AlmaLinux 10 | Stable Enterprise Linux base |
| [**skipjack**](https://github.com/tuna-os/tunaOS) | CentOS Stream 10 | Beta — upstream testing builds |

These are the project's core Enterprise Linux images. See the canonical
[image matrix](https://github.com/tuna-os/tunaOS#choose-your-image) for every
available image family, base distribution, desktop, architecture, and registry
path.

### Desktop and hardware options

Desktop and hardware options vary by image. Common tags combine a desktop such
as `gnome`, `kde`, `cosmic`, or `niri` with an optional hardware suffix such as
`-hwe` or `-nvidia`. Check the image matrix before selecting a tag.

```
ghcr.io/tuna-os/yellowfin:gnome
ghcr.io/tuna-os/albacore:kde-nvidia
ghcr.io/tuna-os/skipjack:gnome-hwe
```

## Key Repositories

| Repo | Purpose |
|---|---|
| [tunaOS](https://github.com/tuna-os/tunaOS) | Main image builder |
| [docs](https://github.com/tuna-os/docs) | Documentation site |
| [tunaos-packages](https://github.com/tuna-os/tunaos-packages) | Cross-distro package factory — RPM + DEB repositories (formerly debian-copr) |

## Archived

The following repositories are **read-only / archived** — they no longer publish
builds or releases. Their documentation pages on
[tunaos.org](https://tunaos.org) are kept for historical reference only:

| Repo | Purpose |
|---|---|
| [chunkah](https://github.com/tuna-os/chunkah) | OCI layer optimization tool (archived) |
| [bonito-x13s](https://github.com/tuna-os/bonito-x13s) | ThinkPad X13s ARM64 image (archived) — see the [Bonito FAQ](https://tunaos.org/docs/faq) |

---

<div align="center">

Built with ❤️ on Enterprise Linux · [tunaos.org](https://tunaos.org) · [Docs](https://github.com/tuna-os/docs)

</div>
