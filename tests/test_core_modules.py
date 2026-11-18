#!/usr/bin/env python3
"""Pruebas unitarias de los módulos de seguridad, estado y utilidades.

Cubren el comportamiento que el panel y el CLI comparten: escritura atómica,
almacenes JSON, perfiles de filtros, sesiones/CSRF, CDP, trabajos persistentes,
exportaciones, grupos, bandeja, programación y estadísticas.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import xrepost_cdp
import xrepost_exports
import xrepost_filters
import xrepost_fs
import xrepost_groups
import xrepost_history
import xrepost_inbox
import xrepost_jobs
import xrepost_schedule
import xrepost_security
import xrepost_stats
import xrepost_store


def write_history(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xrepost-core-")
        self.root = Path(self.tmp.name)
        self.history = self.root / "history.jsonl"

    def tearDown(self):
        self.tmp.cleanup()


class FileSystemTest(Base):
    def test_atomic_write_is_private_and_replaces(self):
        target = self.root / "nested" / "state.json"
        xrepost_fs.atomic_write(target, "primero")
        self.assertEqual(target.read_text(encoding="utf-8"), "primero")
        mode = stat.S_IMODE(target.stat().st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(stat.S_IMODE(target.parent.stat().st_mode), 0o700)
        xrepost_fs.atomic_write(target, "segundo")
        self.assertEqual(target.read_text(encoding="utf-8"), "segundo")

    def test_read_json_handles_missing_corrupt_and_oversize(self):
        self.assertEqual(xrepost_fs.read_json(self.root / "nada.json", default={"x": 1}), {"x": 1})
        bad = self.root / "bad.json"
        bad.write_text("{no json", encoding="utf-8")
        self.assertIsNone(xrepost_fs.read_json(bad))
        big = self.root / "big.json"
        big.write_text("[" + "0" * 200 + "]", encoding="utf-8")
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.read_json(big, max_bytes=32)
        self.assertTrue(xrepost_fs.is_within(self.root, self.root / "a" / "b"))

    def test_safe_join_and_remove_tree_reject_escapes(self):
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.safe_join(self.root, "..", "fuera.txt")
        target = self.root / "runs" / "job"
        target.mkdir(parents=True)
        (target / "f").write_text("x", encoding="utf-8")
        xrepost_fs.remove_tree(target, self.root)
        self.assertFalse(target.exists())
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.remove_tree(self.root.parent, self.root)

    def test_symlinks_are_rejected(self):
        real = self.root / "real.txt"
        real.write_text("x", encoding="utf-8")
        link = self.root / "link.txt"
        link.symlink_to(real)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.atomic_write(link, "y")
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.read_text(link)


class JsonStoreTest(Base):
    def test_default_read_mutate_and_version_guard(self):
        store = xrepost_store.JsonStore(self.root / "doc.json", lambda: {"version": 1, "items": []})
        self.assertEqual(store.read(), {"version": 1, "items": []})
        store.mutate(lambda data: {**data, "items": data["items"] + [1]})
        self.assertEqual(store.read()["items"], [1])

        newer = self.root / "newer.json"
        newer.write_text(json.dumps({"version": 99}), encoding="utf-8")
        with self.assertRaises(ValueError):
            xrepost_store.JsonStore(newer, lambda: {}).read()

    def test_corrupt_file_is_quarantined(self):
        path = self.root / "corrupt.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        store = xrepost_store.JsonStore(path, lambda: {"version": 1})
        self.assertEqual(store.read(), {"version": 1})
        self.assertTrue(store.corrupt_backup)
        self.assertTrue(Path(store.corrupt_backup).exists())


class SecurityTest(Base):
    def test_master_token_length_and_comparison(self):
        with self.assertRaises(ValueError):
            xrepost_security.AuthManager("corto")
        auth = xrepost_security.AuthManager("token-largo")
        self.assertTrue(auth.master_ok("token-largo"))
        self.assertFalse(auth.master_ok("token-largO"))
        self.assertFalse(auth.master_ok(None))

    def test_sessions_rotate_revoke_and_csrf(self):
        auth = xrepost_security.AuthManager("token-largo")
        session = auth.create(client="ip", user_agent="test")
        self.assertIs(auth.get(session.sid), session)
        self.assertTrue(auth.csrf_ok(session, session.csrf))
        self.assertFalse(auth.csrf_ok(session, "otro"))
        rotated = auth.rotate(session.sid, client="ip")
        self.assertIsNotNone(rotated)
        self.assertIsNone(auth.get(session.sid))
        self.assertEqual(rotated.rotations, 1)
        self.assertEqual(auth.count(), 1)
        self.assertTrue(auth.revoke(rotated.sid))
        self.assertEqual(auth.count(), 0)

    def test_expiry_and_bruteforce(self):
        clock = [1000.0]
        auth = xrepost_security.AuthManager(
            "token-largo", ttl=60, idle=10, max_failures=2, window=100, block=30, clock=lambda: clock[0]
        )
        session = auth.create()
        clock[0] += 11
        self.assertIsNone(auth.get(session.sid))
        self.assertEqual(auth.blocked_for("ip"), 0)
        self.assertEqual(auth.register_failure("ip"), 0)
        self.assertEqual(auth.register_failure("ip"), 30)
        self.assertGreater(auth.blocked_for("ip"), 0)
        auth.register_success("ip")
        self.assertEqual(auth.blocked_for("ip"), 0)

    def test_cookie_host_and_origin(self):
        header = xrepost_security.cookie_header("sid", max_age=60)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Strict", header)
        self.assertIn("Max-Age=60", header)
        self.assertIn("Max-Age=0", xrepost_security.clear_cookie_header())
        self.assertTrue(xrepost_security.host_allowed("127.0.0.1:8080", server_port=8080))
        self.assertFalse(xrepost_security.host_allowed("evil.example"))
        self.assertTrue(
            xrepost_security.allowed_origin("http://127.0.0.1:8080", "127.0.0.1:8080", scheme="http")
        )
        self.assertFalse(
            xrepost_security.allowed_origin("http://evil.example", "127.0.0.1:8080", scheme="http")
        )


class CdpTest(unittest.TestCase):
    def test_loopback_endpoint_is_secure(self):
        endpoint = xrepost_cdp.parse_endpoint("http://127.0.0.1:9222")
        self.assertEqual(endpoint.port, 9222)
        self.assertEqual(endpoint.problems, [])
        self.assertEqual(endpoint.base, "http://127.0.0.1:9222")

    def test_remote_or_malformed_endpoint_reports_problems(self):
        endpoint = xrepost_cdp.parse_endpoint("https://10.0.0.5:9222/json")
        self.assertTrue(endpoint.problems)
        text = " ".join(endpoint.problems)
        self.assertIn("esquema", text)
        self.assertIn("loopback", text)
        with self.assertRaises(xrepost_cdp.CdpSecurityError):
            xrepost_cdp.parse_endpoint("http://[::1")


class FiltersTest(Base):
    def test_normalize_and_env(self):
        spec = xrepost_filters.normalize_spec(
            {"include": "cuba, energía", "lang": "es", "min_len": "10", "media": "yes"}
        )
        self.assertEqual(spec["include"], ["cuba", "energía"])
        self.assertEqual(spec["lang"], ["es"])
        self.assertEqual(spec["min_len"], 10)
        env = xrepost_filters.to_env(spec)
        self.assertEqual(env["X_MATCH"], "cuba,energía")
        self.assertEqual(env["X_MEDIA"], "yes")
        with self.assertRaises(xrepost_filters.FilterError):
            xrepost_filters.normalize_spec({"regex": "("})
        with self.assertRaises(xrepost_filters.FilterError):
            xrepost_filters.normalize_spec({"media": "quizá"})

    def test_profiles_crud_and_import_export(self):
        store = xrepost_filters.ProfileStore(self.root / "profiles.json")
        first = store.save("Cuba", {"include": ["cuba"]})
        self.assertEqual(store.get(first["id"])["name"], "Cuba")
        updated = store.save("Cuba energía", {"include": ["cuba", "energía"]}, profile_id=first["id"])
        self.assertEqual(updated["id"], first["id"])
        self.assertEqual(len(store.list()), 1)

        copy = store.duplicate(first["id"], "Copia")
        self.assertEqual(copy["name"], "Copia")

        exported = store.export()
        self.assertEqual(len(exported["profiles"]), 2)
        other = xrepost_filters.ProfileStore(self.root / "otros.json")
        saved = other.import_data(exported)
        self.assertEqual(len(saved), 2)
        self.assertTrue(store.delete(copy["id"]))
        self.assertFalse(store.delete("no-existe"))


class JobsTest(Base):
    def test_job_lifecycle_recover_and_prune(self):
        store = xrepost_jobs.JobStore(self.root / "runs", max_records=2, max_age_days=1)
        created = store.create("a" * 32, "preview", {"users": "@foo", "token": "secreto"})
        self.assertEqual(created["params"]["users"], "@foo")
        self.assertNotIn("token", created["params"])
        store.update(created["id"], state=xrepost_jobs.COMPLETED, post_count=3)
        self.assertEqual(store.get(created["id"])["status"], "done")

        store.create("b" * 32, "apply", {})
        store.update("b" * 32, state=xrepost_jobs.RUNNING)
        interrupted = store.recover()
        self.assertEqual(len(interrupted), 1)
        self.assertEqual(store.get("b" * 32)["state"], xrepost_jobs.INTERRUPTED)

        store.create("c" * 32, "preview", {})
        removed = store.prune(keep={"b" * 32})
        self.assertIn(created["id"], removed)
        self.assertNotIn("b" * 32, removed)

        with self.assertRaises(ValueError):
            store.update("b" * 32, state="inventado")


class ExportsTest(Base):
    def test_csv_neutralizes_formulas_and_markdown_escapes(self):
        rows = [
            {
                "fecha": "2024-01-01",
                "autor": "A|B",
                "usuario": "@foo",
                "texto": "=1+1",
                "url": "https://x.com/foo/status/1",
                "estado": "reposteado",
            }
        ]
        csv_text = xrepost_exports.rows_to_csv(rows)
        self.assertIn("'=1+1", csv_text)
        markdown = xrepost_exports.rows_to_markdown(rows, title="Prueba")
        self.assertIn("A\\|B", markdown)
        html = xrepost_exports.rows_to_html(
            [{"texto": "<script>alert(1)</script>", "url": "javascript:alert(1)"}]
        )
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_pdf_and_bundle_roundtrip(self):
        rows = [{"fecha": "2024-01-01", "autor": "A", "usuario": "@foo", "texto": "hola", "url": "u", "estado": "ok"}]
        pdf = xrepost_exports.rows_to_pdf(rows, title="Informe")
        self.assertTrue(pdf.startswith(b"%PDF"))

        state = self.root / "state"
        state.mkdir()
        (state / "history.jsonl").write_text('{"x": 1}\n', encoding="utf-8")
        (state / "groups.json").write_text('{"version": 1}\n', encoding="utf-8")
        archive = state / "backups" / "bundle.tar.gz"
        bundle = xrepost_exports.backup_bundle(state, archive)
        self.assertIn("history.jsonl", bundle["files"])
        (state / "history.jsonl").write_text("roto\n", encoding="utf-8")
        restored = xrepost_exports.restore_bundle(archive, state)
        self.assertIn("history.jsonl", restored["restored"])
        self.assertIn('{"x": 1}', (state / "history.jsonl").read_text(encoding="utf-8"))


class GroupsTest(Base):
    def test_members_import_export_and_limits(self):
        store = xrepost_groups.GroupStore(self.root / "groups.json")
        group = store.create("Medios", "prueba", ["@foo", "bar", "foo"])
        self.assertEqual([m["handle"] for m in group["members"]], ["foo", "bar"])
        with self.assertRaises(ValueError):
            store.create("medios")

        store.add_members(group["id"], ["baz"])
        self.assertEqual(len(store.get(group["id"])["members"]), 3)
        store.remove_members(group["id"], ["@baz"])
        self.assertEqual([m["handle"] for m in store.get(group["id"])["members"]], ["foo", "bar"])

        parsed = store.import_into(group["id"], "nuevo;Alias\n@otro\n", replace=True)
        self.assertEqual(len(parsed["accounts"]), 2)
        csv_text = store.export_csv(group["id"])
        self.assertIn("grupo,handle,alias", csv_text)
        self.assertIn("nuevo", csv_text)

        meta = xrepost_groups.AccountMetaStore(self.root / "meta.json")
        item = meta.set("foo", alias="Medio", favorite=True)
        self.assertEqual(item["alias"], "Medio")
        self.assertTrue(meta.all()["foo"]["favorite"])
        with self.assertRaises(ValueError):
            meta.set("no válido")

    def test_account_stats_read_history(self):
        write_history(
            self.history,
            [
                {"ts": "2024-01-01T10:00:00+00:00", "action": "repost", "result": "reposted", "search_user": "foo", "id": "1", "url": "u1"},
                {"ts": "2024-01-02T10:00:00+00:00", "action": "repost", "result": "quoted", "search_user": "foo", "id": "2", "url": "u2"},
                {"ts": "2024-01-03T10:00:00+00:00", "action": "undo", "result": "undone", "search_user": "foo", "id": "1", "url": "u1"},
                {"ts": "2024-01-04T10:00:00+00:00", "action": "repost", "result": "unconfirmed", "search_user": "foo", "id": "3", "url": "u3"},
            ],
        )
        stats = xrepost_groups.account_stats(self.history)
        self.assertEqual(stats[0]["reposts"], 1)
        self.assertEqual(stats[0]["quotes"], 1)
        self.assertEqual(stats[0]["undone"], 1)
        self.assertEqual(stats[0]["errors"], 1)


class InboxTest(Base):
    def test_upsert_decision_and_apply_states(self):
        store = xrepost_inbox.InboxStore(self.root / "inbox.json")
        params = {"users": "@foo", "from": "2024-01-01", "to": "2024-01-31", "quote": ""}
        posts = [
            {"url": "https://x.com/foo/status/1", "usuario": "@foo", "autor": "Foo", "texto": "uno", "fecha": "2024-01-01"},
            {"url": "https://x.com/foo/status/2", "usuario": "@foo", "autor": "Foo", "texto": "dos", "fecha": "2024-01-02"},
        ]
        result = store.upsert_from_posts(posts, params, "run")
        self.assertEqual(result["added"], 2)
        self.assertEqual(store.counts()[xrepost_inbox.PENDING], 2)

        store.decide(["1"], xrepost_inbox.APPROVED)
        self.assertEqual(store.counts()[xrepost_inbox.APPROVED], 1)
        self.assertEqual(store.approved_urls(), ["https://x.com/foo/status/1"])

        store.mark(["1"], xrepost_inbox.UNCONFIRMED, "revisar")
        self.assertEqual(store.counts()[xrepost_inbox.UNCONFIRMED], 1)
        # Una decisión humana no puede mover un estado ya ejecutado o incierto.
        store.decide(["1"], xrepost_inbox.PENDING)
        self.assertEqual(store.counts()[xrepost_inbox.PENDING], 1)

        self.assertEqual(store.import_items([{"id": "3", "url": "https://x.com/foo/status/3"}]), 1)
        with self.assertRaises(ValueError):
            store.decide(["2"], "inventado")


class ScheduleTest(Base):
    def test_frequencies_next_run_and_due(self):
        start = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat(timespec="seconds")
        daily = xrepost_schedule.compute_next({"frequency": "daily", "run_at": start})
        self.assertTrue(daily)
        weekly = xrepost_schedule.compute_next({"frequency": "weekly", "run_at": start})
        self.assertTrue(weekly)
        monthly = xrepost_schedule.compute_next({"frequency": "monthly", "run_at": start})
        self.assertTrue(monthly)
        past = "2020-01-01T00:00:00+00:00"
        self.assertEqual(xrepost_schedule.compute_next({"frequency": "once", "run_at": past}), "")

    def test_store_create_update_due_and_mark(self):
        store = xrepost_schedule.ScheduleStore(self.root / "schedules.json")
        run_at = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=30)).isoformat(timespec="seconds")
        item = store.create("Diario", {"users": "@foo", "confirm": True}, frequency="daily", run_at=run_at)
        self.assertEqual(item["mode"], "preview")
        self.assertNotIn("confirm", item["params"])
        with self.assertRaises(ValueError):
            store.create("", {}, frequency="daily", run_at=run_at)
        with self.assertRaises(ValueError):
            store.create("Mala", {}, frequency="hourly", run_at=run_at)
        with self.assertRaises(ValueError):
            store.create("Pasada", {}, frequency="once", run_at="2020-01-01T00:00:00+00:00")

        updated = store.update(item["id"], enabled=False)
        self.assertFalse(updated["enabled"])
        self.assertEqual(store.due(), [])

        store.update(item["id"], enabled=True)
        # Forzamos el vencimiento para probar la selección, sin esperar.
        store.store.mutate(
            lambda data: {
                **data,
                "schedules": [
                    {**entry, "next_run": "2020-01-01T00:00:00+00:00"} if entry["id"] == item["id"] else entry
                    for entry in data["schedules"]
                ],
            }
        )
        self.assertEqual([entry["id"] for entry in store.due()], [item["id"]])
        marked = store.mark_run(item["id"], job_id="job", result="manual")
        self.assertEqual(marked["last_result"], "manual")
        self.assertTrue(store.delete(item["id"]))


class StatsTest(Base):
    def test_rate_never_counts_unknown_as_success(self):
        write_history(
            self.history,
            [
                {"ts": "2024-01-01T10:00:00+00:00", "action": "repost", "result": "reposted", "search_user": "foo", "id": "1", "url": "u1"},
                {"ts": "2024-01-02T10:00:00+00:00", "action": "repost", "result": "unconfirmed", "search_user": "foo", "id": "2", "url": "u2"},
                {"ts": "2024-01-03T10:00:00+00:00", "action": "repost", "result": "no_button", "search_user": "bar", "id": "3", "url": "u3"},
            ],
        )
        data = xrepost_stats.compute(
            self.history,
            jobs=[{"kind": "preview", "post_count": 5, "state": "completed"}],
            inbox=[{"status": "approved"}, {"status": "verified"}, {"status": "rejected"}],
            schedules=[{"enabled": True, "next_run": "2030-01-01T00:00:00+00:00"}],
            days=7,
        )
        self.assertEqual(data["confirmed_total"], 1)
        self.assertEqual(data["unknown"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertEqual(data["rate_denominator"], 3)
        self.assertEqual(data["confirmation_rate"], 33.3)
        self.assertEqual(data["found"], 5)
        self.assertEqual(data["jobs"]["previews"], 1)
        self.assertEqual(data["schedules"]["enabled"], 1)
        self.assertEqual(len(data["daily"]), 7)
        self.assertEqual(data["by_account"][0]["handle"], "foo")
        activity = xrepost_stats.account_activity(self.history, "foo")
        self.assertEqual(activity["total"], 2)
        self.assertTrue(activity["events"][-1]["result"] == "unconfirmed")


class HistoryTest(Base):
    def test_diagnose_backup_and_restore(self):
        write_history(self.history, [
            {"ts": "2024-01-01T00:00:00+00:00", "action": "repost", "result": "reposted", "id": "1", "url": "u1"},
            {"ts": "2024-01-02T00:00:00+00:00", "action": "undo", "result": "undone", "id": "1", "url": "u1"},
        ])
        good = self.history.read_text(encoding="utf-8")
        with self.history.open("a", encoding="utf-8") as fh:
            fh.write("{roto\n")
        report = xrepost_history.diagnose(self.history)
        self.assertEqual(report["corrupt_events"], 1)
        self.assertEqual(report["total_events"], 2)
        self.history.write_text(good, encoding="utf-8")

        backup = xrepost_history.backup(self.history)
        self.assertEqual(backup["events"], 2)
        verified = xrepost_history.verify_backup(backup["path"])
        self.assertTrue(verified["ok"])

        self.history.write_text("", encoding="utf-8")
        restored = xrepost_history.restore(self.history, backup["path"])
        self.assertEqual(restored["diagnostic"]["total_events"], 2)
        self.assertIn("history.pre-restore-", restored["previous"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
