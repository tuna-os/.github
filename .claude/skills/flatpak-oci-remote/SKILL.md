---
name: flatpak-oci-remote
description: Set up a Flatpak remote backed by OCI images on GHCR, or publish new Flatpaks to the tuna-os remote. Covers the index-host-plus-registry architecture, the remote descriptor, client scope rules, signing flags, and the known remote-info 401 trap. Use when setting up, debugging, or documenting a Flatpak remote served over OCI.
---

# Flatpak over OCI (GHCR)

**Prefer the canonical guide over memory.**
[docs/OCI-REMOTE.md](https://github.com/tuna-os/flatpak-index/blob/main/docs/OCI-REMOTE.md)
in `tuna-os/flatpak-index` is the source of truth. I verified every rule
below live against the `tuna-os` remote with flatpak 1.14.6
([tuna-os/flatpak-index#96](https://github.com/tuna-os/flatpak-index/issues/96)).

## 1. Architecture — do not skip this

Never point Flatpak at raw `ghcr.io`. A bare registry is not a remote.
The shape is always three parts:

- App images live on GHCR.
- A Flatpak OCI index (`/index/static`) lives on an HTTPS host.
- Add that host as an `oci+https://` remote.

Flatpak reads the index. Then it pulls blobs from GHCR by digest.
If someone proposes `remote-add` straight at `ghcr.io`, stop. That is
the failure mode.

## 2. Publish a new app

1. Build with `flatpak-builder`. Tag the image with the `org.flatpak.ref`
   label (`app/<id>/<arch>/<branch>`).
2. Push to `ghcr.io/<owner>/<app>` with skopeo or podman.
3. Add the app to the index. Point it at the GHCR manifest digest.
4. Flip the new GHCR package to **public** — new packages default to private,
   and private packages return 401 for anonymous pulls.

## 3. Remote descriptor rules

- `Url=oci+https://<index-host>`; no `AuthenticatorName` on a public setup.
  I verified installs work identically with and without
  `org.flatpak.Authenticator.Oci`, and no authenticator fixes the
  `remote-info` 401. Do not declare one. It sends users down a privileged dead end.

## 4. Client rules that prevent support tickets

- One scope end to end: a `--user` remote needs `install --user` and
  `update --user`; a `--system` remote needs bare commands. Mixed scopes
  report "nothing to update" and look broken.
- Health-check with `remote-ls` or a `--no-deps --no-deploy` install.
  Never use `remote-info`. It 401s on public OCI remotes (bare manifest GET, no
  token handshake; upstream flatpak#6852).
- Unsigned remotes: `--no-gpg-verify`. Signed (flatpak 1.17 and later):
  `--signature-lookaside`. Escape hatch (1.17 and later):
  `flatpak install --image docker://ghcr.io/<owner>/<app>:<tag>`.

## 5. Verify any change to this setup (user scope, no sudo)

```bash
flatpak remote-add --user tuna-os-test https://tunaos.org/flatpak/tuna-os.flatpakrepo
flatpak remote-ls --user tuna-os-test
flatpak install --user --no-deps --no-deploy --noninteractive tuna-os-test <app-id>
flatpak remote-delete --user tuna-os-test
```

Expect `remote-info` to 401 during verification — known limitation above,
not a failure.
