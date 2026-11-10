<div align="center">

<picture>
  <source srcset="https://fonts.gstatic.com/s/e/notoemoji/latest/1f41f/512.webp" type="image/webp">
  <img src="https://fonts.gstatic.com/s/e/notoemoji/latest/1f41f/512.gif" alt="🐟" width="100" height="100">
</picture>

# TunaOS

**Cloud-native Enterprise Linux desktops, the tools that build them, and the applications that ship on them.** [tunaos.org](https://tunaos.org) · [Documentation](https://tunaos.org/docs/intro) · [Download](https://tunaos.org/download) · [Build matrix](https://tunaos.org/matrix)

</div>

---

TunaOS builds desktop operating systems as [bootc](https://containers.github.io/bootc/) OCI images: pull one, boot it, or rebase onto it, with atomic updates and a rollback to the previous image. The images run GNOME, KDE Plasma, COSMIC, Niri, XFCE or Pantheon on AlmaLinux, CentOS Stream, Fedora and several community bases. Around the images sits the rest of the work: a build and boot-test pipeline, a Flatpak remote of GTK4 applications that install on any distribution, package repositories for what Enterprise Linux does not carry yet, and an installer that puts Linux on a Windows machine without repartitioning it. Inspired by [Bluefin](https://projectbluefin.io) and the [Universal Blue](https://universal-blue.org/) community.

## Start here

| If you | Start with |
|---|---|
| Want to help without code | [**Donate time with your AI CLI**](https://hub.tunaos.org/#contribute) — use the hub's existing round-robin setup |
| Run Windows and want to try Linux | [**wootc**](https://github.com/tuna-os/wootc) — installs Linux into a file beside your Windows files, adds a boot entry, and uninstalls by deleting a folder |
| Want an ISO to install | [**Download**](https://tunaos.org/download) — live ISOs for every published image |
| Already run bootc | `sudo bootc switch ghcr.io/tuna-os/albacore:gnome` |
| Want the applications, on any distribution | [**Flatpaks**](https://tunaos.org/flatpak) — the office suite, terminals, a file manager, a Homebrew front end |
| Want to build your own media | [**ISO builder**](https://tunaos.org/iso-builder) — builds a live ISO in the browser |

## The images

Four images cover most people. Each is one base distribution with a choice of desktop.

| Image | Base | For |
|---|---|---|
| [**Albacore**](https://tunaos.org/albacore) | AlmaLinux 10 | A 10-year support cycle. The daily driver |
| [**Yellowfin**](https://tunaos.org/yellowfin) | AlmaLinux Kitten 10 | Newer packages on a near-enterprise base |
| [**Skipjack**](https://tunaos.org/skipjack) | CentOS Stream 10 | A preview of where Enterprise Linux is going |
| [**Bonito**](https://tunaos.org/bonito) | Fedora 44 | The latest packages and kernel |

Other bases — Ubuntu, Arch, Debian, openSUSE, Gentoo, RHEL and the rolling-release siblings — are published too: see [all variants](https://tunaos.org/variants) and the [build matrix](https://tunaos.org/matrix), which shows what is built and what has a live ISO. Tags combine a desktop with an optional hardware suffix:

```
ghcr.io/tuna-os/yellowfin:gnome
ghcr.io/tuna-os/albacore:kde-nvidia
ghcr.io/tuna-os/skipjack:gnome-hwe
```

## Applications

Built in this org and published on the TunaOS Flatpak remote, so they install on any distribution that runs Flatpak.

| Project | What it is |
|---|---|
| [gtk-office-suite](https://github.com/tuna-os/gtk-office-suite) | Letters, Tables and Decks: a word processor, spreadsheet and presentation app in Rust and GTK 4. DOCX, ODT, XLSX, ODS and PPTX in, PDF out. |
| [blueshell](https://github.com/tuna-os/blueshell) | A container-native terminal for GNOME on the Ghostty engine |
| [mariner](https://github.com/tuna-os/mariner) | A GNOME Files alternative — typeahead, dual-pane, Quick Look, full-text search |
| [Tavern](https://github.com/tuna-os/Tavern) | A GTK 4 front end for Homebrew on Linux |
| [mandelbrot](https://github.com/tuna-os/mandelbrot) | A GNOME-native Matrix client with calling, sliding sync and QR login |
| [bluefin-cli](https://github.com/tuna-os/bluefin-cli) | Shell and development-environment setup from the terminal |
| [compass](https://github.com/tuna-os/compass) | A fast, keyboard-first launcher for the Linux desktop, written in Rust |
| [dualcut](https://github.com/tuna-os/dualcut) | A dual-mode video editor: manual multi-track timeline plus a programmatic JSON document |
| [quickcast](https://github.com/tuna-os/quickcast) | Quick GNOME screen recordings with microphone, webcam overlay and automatic file copying |

## Build and delivery

| Project | What it does |
|---|---|
| [tunaOS](https://github.com/tuna-os/tunaOS) | The image factory. Every published desktop image is built here |
| [tacklebox](https://github.com/tuna-os/tacklebox) | Turns bootc images into multi-desktop, deduplicated live ISOs and disk images |
| [iso-builder](https://github.com/tuna-os/iso-builder) | Tacklebox compiled to WebAssembly, so a browser can author an ISO with no build host |
| [corral](https://github.com/tuna-os/corral) | Boots every published image in a real VM and checks it reaches a desktop before promotion |
| [tunaos-packages](https://github.com/tuna-os/tunaos-packages) | The package factory: RPM and DEB repositories for what the bases do not ship |
| [bootc-migrate](https://github.com/tuna-os/bootc-migrate) | In-place migration from OSTree-backed bootc systems to ComposeFS |
| [remora](https://github.com/tuna-os/remora) | Local package layering that survives image updates |
| [wootc](https://github.com/tuna-os/wootc) | Installs a bootc Linux desktop from inside Windows, reversibly |
| [bootc-installer](https://github.com/tuna-os/bootc-installer) | The libadwaita installer for bootc systems, backed by the [fisherman](https://github.com/tuna-os/fisherman) service |
| [bootc-installer-asahi](https://github.com/tuna-os/bootc-installer-asahi) | The Apple Silicon installer path for TunaOS-family bootc images |
| [flatpak-index](https://github.com/tuna-os/flatpak-index) | The central index behind the TunaOS Flatpak remote |
| [branding](https://github.com/tuna-os/branding) | Species marks for installers, ISOs and docs |

Release plumbing ships alongside: [homebrew-tap](https://github.com/tuna-os/homebrew-tap) and [scoop-bucket](https://github.com/tuna-os/scoop-bucket) publish the tools for macOS and Windows, and [bst-ci](https://github.com/tuna-os/bst-ci) carries the shared workflows the image repos build on, with [changelog-action](https://github.com/tuna-os/changelog-action) diffing image package lists for release notes.

## Desktops built from source

[Tromsø](https://github.com/tuna-os/tromso) (KDE) and [XFCE Linux](https://github.com/tuna-os/xfce-linux) are built from source with [BuildStream](https://buildstream.build) on freedesktop-sdk, rather than assembled from prebuilt packages — the same approach as GNOME OS and Project Bluefin's Dakota.

## Prototypes and specs

[protota](https://github.com/tuna-os/protota) is a browser-based mockup tool for Adwaita app UIs; [spindle](https://github.com/tuna-os/spindle) is a design spec for a linearized Matrix homeserver.

## Automation

[Hive](https://github.com/hivecommons/hive) coordinates AI agents across these repositories.
The TunaOS School and Reef hives run on Kubernetes in AWS with Talos Linux nodes.
The [TunaOS fork](https://github.com/tuna-os/hive),
[hive-operator](https://github.com/tuna-os/hive-operator),
[gnome-hive-monitor](https://github.com/tuna-os/gnome-hive-monitor), and
[ccleft](https://github.com/tuna-os/ccleft) provide the platform, Kubernetes
operator, desktop monitor, and agent quota tools.

## Documentation

Every repository's README and docs are synced daily into [tunaos.org](https://tunaos.org/docs/intro), so the site and the source stay in step. [docs](https://github.com/tuna-os/docs) is the site itself.

## Forks

We maintain forks where our builds need them - [PaperWM](https://github.com/tuna-os/PaperWM), [libcosmic](https://github.com/tuna-os/libcosmic), [iced](https://github.com/tuna-os/iced), [rust-atomicwrites](https://github.com/tuna-os/rust-atomicwrites), [rdocx](https://github.com/tuna-os/rdocx) - and send fixes upstream.

## Contributing

<!-- hive-contribute-plea: donated-compute appeal, keep in sync across repos -->
### Contribute compute — no code needed

**[Donate time with your AI CLI](https://hub.tunaos.org/#contribute).**

Your machine runs one task at a time using your signed-in AI coding CLI.
The relay alternates between eligible **School** (OS) and **Reef** (apps)
hives after each task. If one hive has no work, the other can continue.

The guide covers prerequisites, verified `just` setup, credentials, provider
costs, and how to stop with Ctrl+C. Your subscription quota or API charges apply.
Never post account credentials or API keys in issues or pull requests.

For code and documentation changes, follow the
[contribution guide](https://github.com/tuna-os/.github/blob/main/CONTRIBUTING.md)
or choose an [org-wide starter issue](https://github.com/issues?q=org%3Atuna-os+is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22).
To fund the upstream projects TunaOS builds on, see [support](https://tunaos.org/support).

---

<div align="center">

[tunaos.org](https://tunaos.org) · [Docs](https://github.com/tuna-os/docs) · Built on Enterprise Linux

</div>
