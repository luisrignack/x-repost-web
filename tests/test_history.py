#!/usr/bin/env python3
"""Pruebas del estado de historial compartido (motor y panel)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from xrepost_history import history_state, iso_timestamp, tweet_id


def ev(action, result, tid="11", run="r"):
    return {"action": action, "result": result, "id": tid, "run": run,
            "url": f"https://x.com/foo/status/{tid}"}


class HistoryStateTest(unittest.TestCase):
    def test_reposted_is_undoable(self):
        reposted, ours = history_state([ev("repost", "reposted")])
        self.assertEqual(reposted, {"11"})
        self.assertIn("11", ours)

    def test_failed_undo_keeps_post_undoable(self):
        reposted, ours = history_state([
            ev("repost", "reposted"),
            ev("undo", "undo_failed"),
        ])
        self.assertEqual(reposted, {"11"})
        self.assertIn("11", ours)

    def test_successful_undo_clears_state(self):
        reposted, ours = history_state([
            ev("repost", "reposted"),
            ev("undo", "undone"),
        ])
        self.assertEqual(reposted, set())
        self.assertEqual(ours, {})

    def test_not_reposted_undo_clears_state(self):
        reposted, ours = history_state([
            ev("repost", "reposted"),
            ev("undo", "not_reposted"),
        ])
        self.assertEqual(reposted, set())
        self.assertEqual(ours, {})

    def test_quoted_counts_done_but_not_undoable(self):
        reposted, ours = history_state([ev("repost", "quoted")])
        self.assertEqual(reposted, {"11"})
        self.assertEqual(ours, {})

    def test_already_does_not_claim_foreign_repost(self):
        reposted, ours = history_state([ev("repost", "already")])
        self.assertEqual(reposted, {"11"})
        self.assertEqual(ours, {})

    def test_failure_does_not_change_known_state(self):
        reposted, ours = history_state([
            ev("repost", "reposted"),
            ev("repost", "unconfirmed"),
        ])
        self.assertEqual(reposted, {"11"})
        self.assertIn("11", ours)

    def test_repost_after_undo_is_undoable_again(self):
        reposted, ours = history_state([
            ev("repost", "reposted", run="r1"),
            ev("undo", "undone", run="r2"),
            ev("repost", "reposted", run="r3"),
        ])
        self.assertEqual(reposted, {"11"})
        self.assertEqual(ours["11"]["run"], "r3")


class IsoTimestampTest(unittest.TestCase):
    def test_iso_passthrough(self):
        self.assertEqual(iso_timestamp("2024-01-01T10:00:00Z"), "2024-01-01T10:00")
        self.assertEqual(iso_timestamp("2024-01-01"), "2024-01-01")

    def test_dmy_converted(self):
        self.assertEqual(iso_timestamp("01/01/2024 10:00"), "2024-01-01T10:00")
        self.assertEqual(iso_timestamp("01/01/2024"), "2024-01-01")

    def test_empty_and_unknown(self):
        self.assertEqual(iso_timestamp(""), "")
        self.assertEqual(iso_timestamp(None), "")
        self.assertEqual(iso_timestamp("ayer"), "ayer")


class TweetIdTest(unittest.TestCase):
    def test_url_and_bare_id(self):
        self.assertEqual(tweet_id("https://x.com/foo/status/123"), "123")
        self.assertEqual(tweet_id("123"), "123")
        self.assertEqual(tweet_id(""), "")


if __name__ == "__main__":
    unittest.main()