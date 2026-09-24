#!/usr/bin/env python3
"""Tests for update-index.py.

The bug these guard against: this action's copy of the publisher kept only
labels starting with "org.flatpak." when writing an index entry, discarding
the org.freedesktop.appstream.* labels that `flatpak build-bundle --oci`
already writes. Flatpak builds a remote's AppStream catalogue from exactly
those labels, so every app publishing through this action rendered in
software centres as a bare application ID with an "Unknown" licence and no
screenshots (fixed for the KEEP_LABEL_PREFIXES set alone in dc144b4, but the
action never picked up the fuller rewrite -- including --require-appstream --
that landed in tuna-os/flatpak-index's scripts/update-index.py). These tests
mirror flatpak-index's tests/test_update_index.py so the two copies can be
kept in lockstep by inspection.

Plain python3, no test framework -- matches how scripts/ is already run in
this repo's CI (see scripts/test-renovate-automerge-policy.py).
"""

from __future__ import annotations

import base64
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest

_src = pathlib.Path(__file__).with_name("update-index.py")
_spec = importlib.util.spec_from_file_location("update_index", _src)
update_index = importlib.util.module_from_spec(_spec)
sys.modules["update_index"] = update_index
_spec.loader.exec_module(update_index)


# Smallest thing that satisfies a "decodes to a PNG" check.
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16

APPDATA = """<?xml version="1.0" encoding="UTF-8"?>
<components version="0.8" origin="flatpak">
  <component type="desktop-application">
    <id>org.tunaos.example</id>
    <name>Example</name>
    <summary>Do the thing you came for</summary>
    <project_license>MIT</project_license>
  </component>
</components>
"""

ICON = "data:image/png;base64," + base64.b64encode(PNG).decode()

FLATPAK_LABELS = {
    "org.flatpak.ref": "app/org.tunaos.example/x86_64/master",
    "org.flatpak.metadata": "[Application]\nname=org.tunaos.example\n",
    "org.flatpak.commit": "0" * 64,
    "org.flatpak.timestamp": "1780000000",
}

APPSTREAM_LABELS = {
    "org.freedesktop.appstream.appdata": APPDATA,
    "org.freedesktop.appstream.icon-64": ICON,
    "org.freedesktop.appstream.icon-128": ICON,
}


def write_oci_layout(directory, labels, architecture="amd64"):
    """Build a minimal OCI layout the publisher can read."""
    blobs = directory / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)

    config = {
        "architecture": architecture,
        "os": "linux",
        "config": {"Labels": dict(labels)},
    }
    config_bytes = json.dumps(config).encode()
    config_digest = "sha256:" + "c" * 64
    (blobs / config_digest.split(":")[1]).write_bytes(config_bytes)

    manifest = {
        "schemaVersion": 2,
        "config": {"digest": config_digest, "size": len(config_bytes)},
        "layers": [],
    }
    manifest_bytes = json.dumps(manifest).encode()
    manifest_digest = "sha256:" + "m" * 64
    (blobs / manifest_digest.split(":")[1]).write_bytes(manifest_bytes)

    (directory / "index.json").write_text(
        json.dumps({"manifests": [{"digest": manifest_digest}]})
    )
    return manifest_digest


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def build_entry(self, labels, require_appstream=False, architecture="amd64"):
        oci_dir = pathlib.Path(
            tempfile.mkdtemp(dir=self.tmp, prefix=f"oci-{architecture}-")
        )
        digest = write_oci_layout(oci_dir, labels, architecture)
        _, config = update_index.read_oci_layout(oci_dir)
        return digest, update_index.build_image_entry(
            digest, config, ["latest"], require_appstream
        )

    def test_appstream_labels_survive_into_the_index(self):
        _, entry = self.build_entry({**FLATPAK_LABELS, **APPSTREAM_LABELS})
        for label in APPSTREAM_LABELS:
            self.assertIn(label, entry["Labels"], f"{label} was dropped")
        self.assertEqual(
            entry["Labels"]["org.freedesktop.appstream.appdata"], APPDATA
        )

    def test_flatpak_labels_survive_into_the_index(self):
        _, entry = self.build_entry({**FLATPAK_LABELS, **APPSTREAM_LABELS})
        for label in FLATPAK_LABELS:
            self.assertIn(label, entry["Labels"])

    def test_unrelated_labels_are_dropped(self):
        labels = {**FLATPAK_LABELS, "org.opencontainers.image.created": "now"}
        _, entry = self.build_entry(labels)
        self.assertNotIn("org.opencontainers.image.created", entry["Labels"])

    def test_missing_required_flatpak_label_is_an_error(self):
        labels = dict(FLATPAK_LABELS)
        del labels["org.flatpak.ref"]
        with self.assertRaises(ValueError):
            self.build_entry(labels)

    def test_missing_appstream_is_tolerated_by_default(self):
        with contextlib.redirect_stderr(io.StringIO()) as warning:
            _, entry = self.build_entry(FLATPAK_LABELS)
        self.assertIn("metainfo", warning.getvalue())
        self.assertNotIn("org.freedesktop.appstream.appdata", entry["Labels"])

    def test_require_appstream_rejects_an_image_without_metadata(self):
        with self.assertRaises(ValueError) as caught:
            self.build_entry(FLATPAK_LABELS, require_appstream=True)
        self.assertIn("metainfo", str(caught.exception))

    def test_second_architecture_is_added_not_replaced(self):
        index = {"Registry": "https://ghcr.io", "Results": []}
        for arch in ("amd64", "arm64"):
            _, entry = self.build_entry(
                {**FLATPAK_LABELS, **APPSTREAM_LABELS}, architecture=arch
            )
            update_index.merge_entry(index, "tuna-os/example", entry)

        images = index["Results"][0]["Images"]
        self.assertEqual(
            [image["Architecture"] for image in images], ["amd64", "arm64"]
        )

    def test_republishing_one_architecture_replaces_only_that_image(self):
        index = {"Registry": "https://ghcr.io", "Results": []}
        for arch in ("amd64", "arm64"):
            _, entry = self.build_entry(
                {**FLATPAK_LABELS, **APPSTREAM_LABELS}, architecture=arch
            )
            update_index.merge_entry(index, "tuna-os/example", entry)

        _, entry = self.build_entry({**FLATPAK_LABELS, **APPSTREAM_LABELS})
        entry["Digest"] = "sha256:" + "f" * 64
        update_index.merge_entry(index, "tuna-os/example", entry)

        images = index["Results"][0]["Images"]
        self.assertEqual(len(images), 2)
        by_arch = {image["Architecture"]: image["Digest"] for image in images}
        self.assertEqual(by_arch["amd64"], "sha256:" + "f" * 64)
        self.assertTrue(by_arch["arm64"].startswith("sha256:"))

    def test_read_oci_layout_missing_index_file(self):
        missing_dir = self.tmp / "nonexistent-oci"
        with self.assertRaises(FileNotFoundError):
            update_index.read_oci_layout(missing_dir)

    def test_read_oci_layout_empty_manifests(self):
        oci_dir = self.tmp / "empty-manifests-oci"
        oci_dir.mkdir(parents=True, exist_ok=True)
        (oci_dir / "index.json").write_text(json.dumps({"manifests": []}))
        with self.assertRaises(ValueError) as caught:
            update_index.read_oci_layout(oci_dir)
        self.assertIn("No manifests listed", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
