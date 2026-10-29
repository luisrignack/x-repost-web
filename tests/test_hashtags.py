#!/usr/bin/env python3
"""Pruebas de los hashtags recordados y del comentario de la cita."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import xrepost_hashtags as hashtags


class HashtagsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xrepost-hashtags-")
        self.root = Path(self.tmp.name)
        self.store = self.root / "hashtags.json"
        self.history = self.root / "history.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_split_tags(self):
        self.assertEqual(
            hashtags.split_tags("#ETECSA, cuba  ETECSA, mal#tag, ,#"),
            ["ETECSA", "cuba"],
        )
        self.assertEqual(hashtags.split_tags(["#uno", "dos"]), ["uno", "dos"])
        self.assertEqual(hashtags.split_tags(""), [])

    def test_clean_text_turns_words_into_hashtags(self):
        self.assertEqual(hashtags.clean_text("ETECSA, cuba"), "#ETECSA #cuba")
        self.assertEqual(hashtags.clean_text("#Recarga #Datos"), "#Recarga #Datos")
        self.assertEqual(hashtags.clean_text("  "), "")
        self.assertEqual(hashtags.clean_text("!!!"), "")

    def test_resolve_path_next_to_history(self):
        self.assertEqual(
            hashtags.resolve_path(None, self.history),
            self.root / "hashtags.json",
        )
        self.assertEqual(
            hashtags.resolve_path(self.store, self.history),
            self.store,
        )

    def test_add_and_rank_prefix_and_substring(self):
        self.assertTrue(
            hashtags.add_hashtags(["#ETECSA", "RecargaInternacional", "otro"], self.store)
        )
        entries = hashtags.load_hashtags(self.store, self.history)
        self.assertEqual(len(entries), 3)

        found = hashtags.rank_hashtags("etec", entries)
        self.assertEqual([item["tag"] for item in found], ["ETECSA"])

        found = hashtags.rank_hashtags("recarga", entries)
        self.assertEqual([item["tag"] for item in found], ["RecargaInternacional"])

        found = hashtags.rank_hashtags("", entries, exclude={"otro"})
        self.assertNotIn("otro", [item["tag"] for item in found])

    def test_ranking_prefers_recent_and_excludes_used(self):
        self.store.write_text(
            json.dumps(
                {
                    "version": 1,
                    "hashtags": [
                        {"tag": "ETECSA", "count": 9, "last_used": "2026-01-01T00:00:00+00:00"},
                        {"tag": "ETECSA_Cuba", "count": 1, "last_used": "2026-10-01T00:00:00+00:00"},
                        {"tag": "otro", "count": 50, "last_used": "2026-10-01T00:00:00+00:00"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        entries = hashtags.load_hashtags(self.store, self.history)
        found = hashtags.rank_hashtags("etecsa", entries)
        self.assertEqual([item["tag"] for item in found], ["ETECSA", "ETECSA_Cuba"])

        found = hashtags.rank_hashtags("", entries, exclude={"otro"})
        self.assertEqual(found[0]["tag"], "ETECSA_Cuba")

    def test_add_increments_and_keeps_case(self):
        hashtags.add_hashtags("#Etecsa", self.store)
        hashtags.add_hashtags("#etecsa", self.store)
        data = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual(data["hashtags"][0]["tag"], "etecsa")
        self.assertEqual(data["hashtags"][0]["count"], 2)
        self.assertEqual(len(data["hashtags"]), 1)

    def test_invalid_values_are_ignored(self):
        self.assertFalse(hashtags.add_hashtags("!!!", self.store))
        self.assertFalse(self.store.exists())

        hashtags.add_hashtags("#ok", self.store)
        hashtags.add_hashtags("#" * 5, self.store)
        data = json.loads(self.store.read_text(encoding="utf-8"))
        self.assertEqual([item["tag"] for item in data["hashtags"]], ["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
