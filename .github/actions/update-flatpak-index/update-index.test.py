#!/usr/bin/env python3
"""Tests for update-index.py, the org's canonical Flatpak index publisher.

This script is the migration target for every tuna-os application repo's
publish workflow. It runs with `packages: write` and a token that can push to
the served index, and it is the last step before a release becomes visible in
software centres -- so a defect here is a bad or missing catalogue entry for an
image that already landed in the registry.

Until now nothing in this repository executed it. `tuna-os/flatpak-index` has
a suite for its byte-identical copy, but a suite in another repository cannot
gate a change made here: a commit to this file reaches every consumer at their
next run, because callers pin `@main`.

The guarded behaviours, in the order they matter:

- Label filtering. An earlier revision kept only `org.flatpak.*` and silently
  dropped `org.freedesktop.appstream.*`, which is what Flatpak builds a
  remote's AppStream catalogue from. Every app then rendered as a bare
  application ID with no icon, licence or screenshots.
- Per-architecture merge. `publish-flatpak-index` replays this script on a
  freshly cloned index each time it loses a push race, so "replace only my own
  architecture, leave every other entry alone" is what makes that retry loop
  safe. If a replay dropped a sibling entry, the loser of a race would delete
  the winner's release.
- Malformed input. The script merges into an index file other publishers also
  write. A structurally surprising entry must produce a diagnosable error, not
  a bare KeyError traceback.

Plain `unittest`, standard library only -- matching how `scripts/` is already
run in CI, and keeping the action's one-file no-dependency property.

Run: python3 .github/actions/update-flatpak-index/update-index.test.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

_SRC = Path(__file__).with_name("update-index.py")
_spec = importlib.util.spec_from_file_location("update_index", _SRC)
update_index = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_index)


FLATPAK_LABELS = {
    "org.flatpak.ref": "app/org.tunaos.Example/x86_64/stable",
    "org.flatpak.metadata": "[Application]\nname=org.tunaos.Example\n",
}

APPSTREAM_LABELS = {
    "org.freedesktop.appstream.appdata": "<components/>",
    "org.freedesktop.appstream.icon-64": "aGVsbG8=",
    "org.freedesktop.appstream.icon-128": "aGVsbG8=",
}


def oci_layout(tmp: Path, *, architecture: str = "amd64", labels: dict, name: str = "oci") -> Path:
    """Write a minimal OCI layout the script can read, and return its path.

    Only the parts `read_oci_layout` walks are produced: index.json naming one
    manifest, the manifest naming a config, and the config carrying Labels.
    Digests are the literal blob file names, so nothing here depends on
    matching a real content hash.
    """
    root = tmp / name
    blobs = root / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)

    config = {
        "os": "linux",
        "architecture": architecture,
        "config": {"Labels": dict(labels)},
    }
    config_digest = f"config-{architecture}"
    (blobs / config_digest).write_text(json.dumps(config), encoding="utf-8")

    manifest = {"config": {"digest": f"sha256:{config_digest}"}}
    manifest_digest = f"manifest-{architecture}"
    (blobs / manifest_digest).write_text(json.dumps(manifest), encoding="utf-8")

    (root / "index.json").write_text(
        json.dumps({"manifests": [{"digest": f"sha256:{manifest_digest}"}]}),
        encoding="utf-8",
    )
    return root


def publish(oci_dir: Path, index_file: Path, repo_name: str, *, tags=("latest",),
            require_appstream: bool = False) -> str:
    """Run the script's main() as a workflow would, returning its stderr."""
    argv = [
        "update-index.py",
        "--oci-dir", str(oci_dir),
        "--index-file", str(index_file),
        "--repo-name", repo_name,
        "--tags", *tags,
    ]
    if require_appstream:
        argv.append("--require-appstream")

    err = io.StringIO()
    old = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            update_index.main()
    finally:
        sys.argv = old
    return err.getvalue()


def images_for(index_file: Path, repo_name: str) -> list[dict]:
    data = json.loads(index_file.read_text(encoding="utf-8"))
    for result in data["Results"]:
        if result["Name"] == repo_name:
            return result["Images"]
    raise AssertionError(f"{repo_name} is absent from {index_file}")


class LabelFilteringTests(unittest.TestCase):
    """What reaches the index decides what a software centre can show."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.index = self.tmp / "index" / "static"

    def test_appstream_labels_survive_into_the_index(self):
        oci = oci_layout(self.tmp, labels={**FLATPAK_LABELS, **APPSTREAM_LABELS})
        publish(oci, self.index, "tuna-os/example")
        labels = images_for(self.index, "tuna-os/example")[0]["Labels"]
        for key, value in APPSTREAM_LABELS.items():
            self.assertEqual(labels.get(key), value, f"{key} must reach the index")

    def test_flatpak_labels_survive_into_the_index(self):
        oci = oci_layout(self.tmp, labels={**FLATPAK_LABELS, **APPSTREAM_LABELS})
        publish(oci, self.index, "tuna-os/example")
        labels = images_for(self.index, "tuna-os/example")[0]["Labels"]
        for key, value in FLATPAK_LABELS.items():
            self.assertEqual(labels.get(key), value, f"{key} must reach the index")

    def test_unrelated_labels_are_dropped(self):
        oci = oci_layout(self.tmp, labels={
            **FLATPAK_LABELS,
            **APPSTREAM_LABELS,
            "org.opencontainers.image.created": "2026-01-01T00:00:00Z",
            "maintainer": "someone@example.com",
        })
        publish(oci, self.index, "tuna-os/example")
        labels = images_for(self.index, "tuna-os/example")[0]["Labels"]
        self.assertNotIn("org.opencontainers.image.created", labels)
        self.assertNotIn("maintainer", labels)


class RequiredMetadataTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.index = self.tmp / "index" / "static"

    def test_missing_required_flatpak_label_is_an_error(self):
        # Without org.flatpak.ref, Flatpak cannot resolve or install the ref:
        # an entry like this is worse than no entry, so it must not publish.
        oci = oci_layout(self.tmp, labels={
            "org.flatpak.metadata": FLATPAK_LABELS["org.flatpak.metadata"],
            **APPSTREAM_LABELS,
        })
        with self.assertRaises(ValueError) as caught:
            publish(oci, self.index, "tuna-os/example")
        self.assertIn("org.flatpak.ref", str(caught.exception))

    def test_missing_appstream_warns_but_still_publishes_by_default(self):
        # A warning, not a failure: an app with no metainfo.xml yet is still
        # installable, and a hard failure here would block its release.
        oci = oci_layout(self.tmp, labels=dict(FLATPAK_LABELS))
        stderr = publish(oci, self.index, "tuna-os/example")
        self.assertIn("No AppStream metadata", stderr)
        self.assertEqual(len(images_for(self.index, "tuna-os/example")), 1)

    def test_require_appstream_rejects_an_image_without_metadata(self):
        oci = oci_layout(self.tmp, labels=dict(FLATPAK_LABELS))
        with self.assertRaises(ValueError) as caught:
            publish(oci, self.index, "tuna-os/example", require_appstream=True)
        self.assertIn("No AppStream metadata", str(caught.exception))
        self.assertFalse(self.index.exists(), "a rejected image must not be written")


class MergeTests(unittest.TestCase):
    """The property that makes publish-flatpak-index's retry loop safe."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.index = self.tmp / "index" / "static"
        self.labels = {**FLATPAK_LABELS, **APPSTREAM_LABELS}

    def test_second_architecture_is_added_not_replaced(self):
        publish(oci_layout(self.tmp, architecture="amd64", labels=self.labels, name="a"),
                self.index, "tuna-os/example")
        publish(oci_layout(self.tmp, architecture="arm64", labels=self.labels, name="b"),
                self.index, "tuna-os/example")
        arches = [i["Architecture"] for i in images_for(self.index, "tuna-os/example")]
        self.assertEqual(arches, ["amd64", "arm64"])

    def test_republishing_one_architecture_replaces_only_that_image(self):
        publish(oci_layout(self.tmp, architecture="amd64", labels=self.labels, name="a"),
                self.index, "tuna-os/example")
        publish(oci_layout(self.tmp, architecture="arm64", labels=self.labels, name="b"),
                self.index, "tuna-os/example")

        # Re-publish amd64 with a changed ref, as a second release would.
        changed = dict(self.labels)
        changed["org.flatpak.ref"] = "app/org.tunaos.Example/x86_64/beta"
        publish(oci_layout(self.tmp, architecture="amd64", labels=changed, name="c"),
                self.index, "tuna-os/example")

        images = images_for(self.index, "tuna-os/example")
        self.assertEqual([i["Architecture"] for i in images], ["amd64", "arm64"],
                         "re-publishing one arch must not add or drop an entry")
        by_arch = {i["Architecture"]: i for i in images}
        self.assertEqual(by_arch["amd64"]["Labels"]["org.flatpak.ref"],
                         "app/org.tunaos.Example/x86_64/beta")
        self.assertEqual(by_arch["arm64"]["Labels"]["org.flatpak.ref"],
                         FLATPAK_LABELS["org.flatpak.ref"],
                         "the sibling architecture must be untouched")

    def test_another_apps_entry_is_left_alone(self):
        # The index is shared: every app publishes into the same file, and the
        # retry loop replays this script on whatever tip it re-cloned.
        publish(oci_layout(self.tmp, labels=self.labels, name="a"),
                self.index, "tuna-os/first")
        publish(oci_layout(self.tmp, labels=self.labels, name="b"),
                self.index, "tuna-os/second")
        data = json.loads(self.index.read_text(encoding="utf-8"))
        self.assertEqual([r["Name"] for r in data["Results"]],
                         ["tuna-os/first", "tuna-os/second"])

    def test_an_app_is_indexed_under_its_repo_name_not_its_app_id(self):
        # Flatpak resolves the image by registry repository, so the Name key
        # must be the repo -- the app ID only appears inside the labels.
        oci = oci_layout(self.tmp, labels=self.labels)
        publish(oci, self.index, "tuna-os/example")
        data = json.loads(self.index.read_text(encoding="utf-8"))
        self.assertEqual([r["Name"] for r in data["Results"]], ["tuna-os/example"])

    def test_registry_field_is_written_for_a_new_index(self):
        oci = oci_layout(self.tmp, labels=self.labels)
        publish(oci, self.index, "tuna-os/example")
        data = json.loads(self.index.read_text(encoding="utf-8"))
        self.assertEqual(data["Registry"], "https://ghcr.io")


class MalformedInputTests(unittest.TestCase):
    """A bad index or layout must be diagnosable from the job log."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.index = self.tmp / "index" / "static"
        self.labels = {**FLATPAK_LABELS, **APPSTREAM_LABELS}

    def test_missing_index_json_names_the_directory(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with self.assertRaises(FileNotFoundError) as caught:
            publish(empty, self.index, "tuna-os/example")
        self.assertIn("index.json", str(caught.exception))

    def test_layout_with_no_manifests_is_an_error(self):
        oci = oci_layout(self.tmp, labels=self.labels)
        (oci / "index.json").write_text(json.dumps({"manifests": []}), encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            publish(oci, self.index, "tuna-os/example")
        self.assertIn("No manifests", str(caught.exception))

    def test_existing_result_without_images_is_reported_not_a_keyerror(self):
        # A hand-edited or older-schema entry. KeyError('Images') in a
        # publish job tells the reader nothing about which file is wrong.
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.index.write_text(json.dumps({
            "Registry": "https://ghcr.io",
            "Results": [{"Name": "tuna-os/example"}],
        }), encoding="utf-8")
        oci = oci_layout(self.tmp, labels=self.labels)
        with self.assertRaises(ValueError) as caught:
            publish(oci, self.index, "tuna-os/example")
        self.assertIn("Images", str(caught.exception))

    def test_existing_result_without_name_is_reported_not_a_keyerror(self):
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.index.write_text(json.dumps({
            "Registry": "https://ghcr.io",
            "Results": [{"Images": []}],
        }), encoding="utf-8")
        oci = oci_layout(self.tmp, labels=self.labels)
        with self.assertRaises(ValueError) as caught:
            publish(oci, self.index, "tuna-os/example")
        self.assertIn("Name", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
