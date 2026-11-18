#!/usr/bin/env python3
"""Pruebas unitarias de los módulos de seguridad, estado y utilidades.

Cubren el comportamiento que el panel y el CLI comparten: escritura atómica,
almacenes JSON, perfiles de filtros, sesiones/CSRF, CDP, trabajos persistentes,
exportaciones, grupos, bandeja, programación y estadísticas.
"""

from __future__ import annotations

import datetime as dt
import contextlib
import errno
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from unittest import mock
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
import xrepost_state
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


class StateMachineTest(Base):
    def test_transiciones_validas_y_terminales(self):
        self.assertTrue(xrepost_state.can(xrepost_state.DISCOVERED, xrepost_state.SELECTED))
        self.assertTrue(xrepost_state.can(xrepost_state.SELECTED, xrepost_state.EXECUTING))
        self.assertTrue(xrepost_state.can(xrepost_state.EXECUTING, xrepost_state.CONFIRMED))
        self.assertTrue(xrepost_state.can(xrepost_state.CONFIRMED, xrepost_state.UNDO_PENDING))
        self.assertTrue(xrepost_state.can(xrepost_state.UNDO_PENDING, xrepost_state.UNDONE))
        # Idempotente, pero un terminal no vuelve a ejecutarse.
        self.assertTrue(xrepost_state.can(xrepost_state.UNDONE, xrepost_state.UNDONE))
        self.assertFalse(xrepost_state.can(xrepost_state.UNDONE, xrepost_state.PENDING))
        self.assertFalse(xrepost_state.can(xrepost_state.DISCOVERED, xrepost_state.CONFIRMED))
        with self.assertRaises(xrepost_state.TransitionError):
            xrepost_state.require(xrepost_state.DISCOVERED, xrepost_state.CONFIRMED)

    def test_etiquetas_historicas_y_normalizacion(self):
        self.assertEqual(xrepost_state.state_for("approved"), xrepost_state.SELECTED)
        self.assertEqual(xrepost_state.state_for("verified"), xrepost_state.CONFIRMED)
        self.assertEqual(xrepost_state.state_for("queued"), xrepost_state.EXECUTING)
        self.assertEqual(xrepost_state.state_for("desconocido"), xrepost_state.DISCOVERED)
        self.assertEqual(
            xrepost_state.normalize(None, "unconfirmed"), xrepost_state.UNCONFIRMED
        )
        self.assertEqual(
            xrepost_state.history_summary(["verified", "failed", "verified"]),
            {
                **{state: 0 for state in xrepost_state.STATES},
                xrepost_state.CONFIRMED: 2,
                xrepost_state.FAILED: 1,
            },
        )

    def test_bandeja_expone_estado_canonico(self):
        store = xrepost_inbox.InboxStore(self.root / "inbox.json")
        params = {"users": "@foo", "from": "2024-01-01", "to": "2024-01-31"}
        posts = [{"url": "https://x.com/foo/status/9", "usuario": "@foo", "texto": "nueve"}]
        store.upsert_from_posts(posts, params, "run")
        self.assertEqual(store.get("9")["state"], xrepost_state.DISCOVERED)
        store.decide(["9"], xrepost_inbox.APPROVED)
        self.assertEqual(store.get("9")["state"], xrepost_state.SELECTED)
        store.mark(["9"], xrepost_inbox.QUEUED)
        self.assertEqual(store.get("9")["state"], xrepost_state.EXECUTING)
        store.mark(["9"], xrepost_inbox.VERIFIED, "confirmado en X")
        self.assertEqual(store.get("9")["state"], xrepost_state.CONFIRMED)
        with self.assertRaises(xrepost_state.TransitionError):
            store.mark(["9"], xrepost_inbox.PENDING)


class FilesystemHardeningTest(Base):
    def test_ensure_dir_private_and_rejects_symlink(self):
        target = self.root / "private" / "deep"
        created = xrepost_fs.ensure_dir(target)
        self.assertTrue(created.is_dir())
        self.assertEqual(stat.S_IMODE(created.stat().st_mode), 0o700)

        link = self.root / "enlace"
        link.symlink_to(created, target_is_directory=True)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.ensure_dir(link)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.assert_regular_file(link)

        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.assert_regular_file(created)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.assert_regular_file(self.root / "no-existe")

    def test_atomic_write_permisos_y_contenido(self):
        dest = self.root / "datos" / "archivo.json"
        xrepost_fs.atomic_write(dest, '{"a": 1}')
        self.assertEqual(dest.read_text(encoding="utf-8"), '{"a": 1}')
        self.assertEqual(stat.S_IMODE(dest.stat().st_mode), 0o600)

        link = self.root / "datos" / "enlace.json"
        link.symlink_to(dest)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.atomic_write(link, "x")

        json_path = xrepost_fs.write_json(self.root / "datos" / "b.json", {"b": 2})
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["b"], 2)

    def test_lectura_con_limites_y_corrupcion(self):
        path = self.root / "texto.txt"
        path.write_text("hola", encoding="utf-8")
        self.assertEqual(xrepost_fs.read_text(path), "hola")
        self.assertEqual(xrepost_fs.read_text(self.root / "falta.txt", default="x"), "x")
        self.assertIsNone(xrepost_fs.read_text(self.root / "falta.txt"))
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.read_text(path, max_bytes=1)

        link = self.root / "texto-enlace.txt"
        link.symlink_to(path)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.read_text(link)

        self.assertEqual(xrepost_fs.read_json(path, default={"x": 1}), {"x": 1})
        bad = self.root / "mal.json"
        bad.write_text("{roto", encoding="utf-8")
        self.assertEqual(xrepost_fs.read_json(bad, default={"y": 2}), {"y": 2})

    def test_append_line_bloqueo_y_enlace(self):
        path = self.root / "eventos.jsonl"
        xrepost_fs.append_line(path, "uno")
        xrepost_fs.append_line(path, "dos\n")
        self.assertEqual(path.read_text(encoding="utf-8"), "uno\ndos\n")
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

        link = self.root / "eventos-enlace.jsonl"
        link.symlink_to(path)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.append_line(link, "tres")

        with xrepost_fs.locked(self.root / "x.lock", exclusive=False):
            self.assertTrue((self.root / "x.lock").exists())

    def test_rutas_y_borrado_seguro(self):
        base = self.root / "base"
        xrepost_fs.ensure_dir(base)
        self.assertEqual(xrepost_fs.safe_join(base, "a", "b"), base / "a" / "b")
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.safe_join(base, "..", "fuera")
        self.assertTrue(xrepost_fs.is_within(base, base / "a"))
        self.assertFalse(xrepost_fs.is_within(base, self.root))

        inside = base / "dentro"
        xrepost_fs.ensure_dir(inside / "sub")
        xrepost_fs.remove_tree(inside, base)
        self.assertFalse(inside.exists())
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.remove_tree(self.root / "ajeno", base)
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.remove_tree(base, base)

        otro = base / "otro"
        otro.write_text("x", encoding="utf-8")
        link = base / "enlace"
        link.symlink_to(otro)
        xrepost_fs.remove_tree(link, base)
        self.assertFalse(link.is_symlink())
        self.assertTrue(otro.exists())
        fuera = base / "fuera"
        fuera.symlink_to(self.root / "ajeno")
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.remove_tree(fuera, base)

    def test_tamanos_y_flags(self):
        path = self.root / "dato.bin"
        path.write_bytes(b"12345")
        self.assertEqual(xrepost_fs.file_size(path), 5)
        self.assertEqual(xrepost_fs.file_size(self.root / "no.bin"), 0)
        xrepost_fs.ensure_private_file(path)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        flags = xrepost_fs.no_follow_open_flags()
        self.assertTrue(flags & os.O_APPEND)
        if hasattr(os, "O_NOFOLLOW"):
            self.assertTrue(flags & os.O_NOFOLLOW)
        self.assertIn("enlace", xrepost_fs.describe_error(OSError(errno.ELOOP, "loop")))
        self.assertIn("x", xrepost_fs.describe_error(OSError(errno.EIO, "x")))

    def test_assert_owned_rechaza_error(self):
        with self.assertRaises(xrepost_fs.UnsafePathError):
            xrepost_fs.assert_owned(self.root / "no-existe")


class FiltersAndProfilesTest(Base):
    def test_compile_safe_valida(self):
        self.assertIsNone(xrepost_filters.compile_safe(""))
        self.assertIsNotNone(xrepost_filters.compile_safe("hola"))
        for pattern in ("a" * 201, "(a+)+", "(a|aa)+", "a{500}", "("):
            with self.assertRaises(xrepost_filters.FilterError):
                xrepost_filters.compile_safe(pattern)

    def test_normalize_spec_y_errores(self):
        spec = xrepost_filters.normalize_spec(
            {"include": "Uno, uno, ,dos", "min_len": "2", "max_len": 10, "media": "sí"}
        )
        self.assertEqual(spec["include"], ["uno", "dos"])
        self.assertEqual(spec["min_len"], 2)
        self.assertEqual(spec["media"], "yes")
        self.assertEqual(xrepost_filters.normalize_spec({})["min_len"], 0)

        invalid = [
            {"min_len": 5, "max_len": 2},
            {"min_len": "x"},
            {"min_len": 20000},
            {"media": "quizá"},
            {"regex": "(a+)+"},
        ]
        for data in invalid:
            with self.assertRaises(xrepost_filters.FilterError):
                xrepost_filters.normalize_spec(data)

    def test_post_matches_todos_los_criterios(self):
        post = {
            "texto": "Hola #Cuba con foto y vídeo",
            "lang": "es-ES",
            "media": True,
            "video": True,
            "reply": False,
            "ctx": "",
        }
        cases = [
            ({"include": "hola"}, True),
            ({"include": "adios"}, False),
            ({"exclude": "cuba"}, False),
            ({"exact": "foto"}, True),
            ({"regex": r"h[oa]la"}, True),
            ({"exclude_regex": "cuba"}, False),
            ({"lang": "es"}, True),
            ({"lang": "en"}, False),
            ({"hashtags": "cuba"}, True),
            ({"hashtags": "otro"}, False),
            ({"min_len": 100}, False),
            ({"max_len": 3}, False),
            ({"media": "yes"}, True),
            ({"media": "no"}, False),
            ({"video": "yes"}, True),
            ({"kind": "original"}, True),
            ({"kind": "reply"}, False),
            ({"kind": "retweet"}, False),
        ]
        for raw, expected in cases:
            spec = xrepost_filters.normalize_spec(raw)
            self.assertEqual(xrepost_filters.post_matches(post, spec), expected, raw)

        self.assertTrue(xrepost_filters.post_matches(post, None))
        self.assertFalse(
            xrepost_filters.post_matches({"texto": "x", "ctx": "repost"}, xrepost_filters.normalize_spec({"kind": "original"}))
        )
        self.assertTrue(
            xrepost_filters.post_matches({"texto": "x", "retweet": True}, xrepost_filters.normalize_spec({"kind": "retweet"}))
        )

    def test_to_env_contrato(self):
        spec = xrepost_filters.normalize_spec({"include": "uno", "lang": "es", "hashtags": "#cuba"})
        env = xrepost_filters.to_env(spec)
        self.assertEqual(env["X_MATCH"], "uno")
        self.assertEqual(env["X_LANG"], "es")
        self.assertEqual(env["X_HASHTAGS_FILTER"], "#cuba")

    def test_perfiles_crud_export_import(self):
        store = xrepost_filters.ProfileStore(self.root / "profiles.json")
        saved = store.save("Tecnología", {"include": "cuba"})
        self.assertEqual(saved["name"], "Tecnología")
        self.assertEqual(len(store.list()), 1)
        self.assertEqual(store.get(saved["id"])["name"], "Tecnología")
        self.assertIsNone(store.get("no-existe"))

        copy = store.duplicate(saved["id"])
        self.assertIn("copia", copy["name"])
        with self.assertRaises(KeyError):
            store.duplicate("no-existe")

        exported = store.export()
        self.assertEqual(len(exported["profiles"]), 2)
        self.assertEqual(len(store.export(saved["id"])["profiles"]), 1)
        with self.assertRaises(KeyError):
            store.export("no-existe")

        imported = store.import_data({"profiles": [{"name": "Importado", "filters": {"include": "x"}}]})
        self.assertEqual(imported[0]["name"], "Importado")
        with self.assertRaises(xrepost_filters.FilterError):
            store.import_data({"nada": []})

        self.assertTrue(store.delete(saved["id"]))
        self.assertFalse(store.delete(saved["id"]))
        with self.assertRaises(xrepost_filters.FilterError):
            store.save("", {})

        path = self.root / "perfiles-export.json"
        xrepost_fs.write_json(path, exported)
        self.assertEqual(len(xrepost_filters.load_export_file(path)["profiles"]), 2)
        bad = self.root / "perfiles-mal.json"
        bad.write_text("{roto", encoding="utf-8")
        with self.assertRaises(xrepost_filters.FilterError):
            xrepost_filters.load_export_file(bad)
        arr = self.root / "perfiles-array.json"
        arr.write_text("[]", encoding="utf-8")
        with self.assertRaises(xrepost_filters.FilterError):
            xrepost_filters.load_export_file(arr)

    def test_limite_de_perfiles(self):
        store = xrepost_filters.ProfileStore(self.root / "profiles.json")
        with mock.patch.object(xrepost_filters, "MAX_PROFILES", 2):
            store.save("uno", {})
            store.save("dos", {})
            with self.assertRaises(xrepost_filters.FilterError):
                store.save("tres", {})


class CdpSecurityTest(Base):
    def test_parse_endpoint_valida(self):
        parsed = xrepost_cdp.parse_endpoint("http://127.0.0.1:9222")
        self.assertEqual(parsed.problems, [])
        self.assertEqual((parsed.host, parsed.port), ("127.0.0.1", 9222))

        problems = xrepost_cdp.parse_endpoint("https://user:pass@example.com:9222/x?y=1").problems
        self.assertTrue(any("esquema" in item for item in problems))
        self.assertTrue(any("credenciales" in item for item in problems))
        self.assertTrue(any("ruta" in item for item in problems))
        self.assertTrue(any("loopback" in item for item in problems))

        self.assertTrue(any("puerto" in item for item in xrepost_cdp.parse_endpoint("http://127.0.0.1").problems))
        self.assertTrue(any("fuera de rango" in item for item in xrepost_cdp.parse_endpoint("http://127.0.0.1:0").problems))

        self.assertTrue(xrepost_cdp._is_loopback_ip("::1"))
        self.assertTrue(xrepost_cdp._is_loopback_ip("localhost"))
        self.assertFalse(xrepost_cdp._is_loopback_ip("10.0.0.1"))

    def test_probe_contra_servidor_local(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        payload = {}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                raw = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = xrepost_cdp.parse_endpoint(f"http://127.0.0.1:{server.server_port}")

            payload = {"Browser": "Chrome/130", "webSocketDebuggerUrl": f"ws://127.0.0.1:{server.server_port}/devtools/browser/x"}
            ok = xrepost_cdp.probe(endpoint)
            self.assertTrue(ok["ok"], ok)

            payload = {"Browser": "Firefox", "webSocketDebuggerUrl": "ws://example.com:1/x"}
            bad = xrepost_cdp.probe(endpoint)
            self.assertFalse(bad["ok"])
            self.assertTrue(any("Chrome" in item for item in bad["problems"]))
            self.assertTrue(any("loopback" in item for item in bad["problems"]))
            self.assertTrue(any("otro puerto" in item for item in bad["problems"]))

            payload = {"Browser": "", "webSocketDebuggerUrl": ""}
            empty = xrepost_cdp.probe(endpoint)
            self.assertFalse(empty["ok"])
            self.assertTrue(any("no identifica" in item for item in empty["problems"]))

            payload = {}
            not_object = xrepost_cdp.probe(endpoint)
            self.assertFalse(not_object["ok"])
        finally:
            server.shutdown()
            server.server_close()

        closed = xrepost_cdp.parse_endpoint("http://127.0.0.1:1")
        error = xrepost_cdp.probe(closed, timeout=0.2)
        self.assertFalse(error["ok"])
        self.assertTrue(error["problems"])

        self.assertFalse(xrepost_cdp.quick_available("http://0.0.0.0:9222"))
        with mock.patch.object(xrepost_cdp, "probe", return_value={"ok": True}):
            self.assertTrue(xrepost_cdp.quick_available("http://127.0.0.1:9222"))

    def test_status_bloquea_y_requiere(self):
        report = xrepost_cdp.status("http://10.0.0.5:9222")
        self.assertFalse(report["secure"])
        self.assertFalse(report["reachable"])
        with self.assertRaises(xrepost_cdp.CdpSecurityError):
            xrepost_cdp.require_ready("http://10.0.0.5:9222")

        with mock.patch.object(xrepost_cdp, "_listening_addresses", return_value=["0.0.0.0"]), \
             mock.patch.object(xrepost_cdp, "chrome_processes", return_value=[
                 {"pid": 1, "exe": "chrome", "profile": "/otro", "profile_ok": False},
                 {"pid": 2, "exe": "chrome", "profile": "", "profile_ok": False},
             ]), \
             mock.patch.object(xrepost_cdp, "probe", return_value={"ok": True, "browser": "Chrome", "websocket": "", "problems": []}):
            report = xrepost_cdp.status("http://127.0.0.1:9222", profile=self.root / "perfil")
            self.assertFalse(report["secure"])
            self.assertTrue(any("no es loopback" in item for item in report["problems"]))
            self.assertTrue(any("2 procesos" in item for item in report["problems"]))
            self.assertTrue(any("otro perfil" in item for item in report["problems"]))
            self.assertTrue(any("no declara" in item for item in report["problems"]))

        with mock.patch.object(xrepost_cdp, "_listening_addresses", return_value=["127.0.0.1"]), \
             mock.patch.object(xrepost_cdp, "chrome_processes", return_value=[
                 {"pid": 1, "exe": "chrome", "profile": str(self.root / "perfil"), "profile_ok": True},
             ]), \
             mock.patch.object(xrepost_cdp, "probe", return_value={"ok": True, "browser": "Chrome", "websocket": "", "problems": []}):
            report = xrepost_cdp.status("http://127.0.0.1:9222", profile=self.root / "perfil")
            self.assertTrue(report["secure"], report["problems"])

    def test_helpers_de_proceso_y_salida(self):
        self.assertIsInstance(xrepost_cdp._listening_addresses(1), list)
        self.assertIsInstance(xrepost_cdp.chrome_processes(1), list)
        self.assertTrue(xrepost_cdp._profile_is_personal(Path.home() / ".config" / "google-chrome"))
        self.assertFalse(xrepost_cdp._profile_is_personal(self.root / "perfil"))
        self.assertEqual(xrepost_cdp.default_profile(), Path(os.environ.get("XREPOST_CHROME_PROFILE", Path.home() / ".local/state/xrepost/chrome-profile")).expanduser().resolve())

        report = {"secure": True, "reachable": True, "url": "http://127.0.0.1:9222", "profile": "/p", "problems": []}
        out = io.StringIO()
        with mock.patch.object(xrepost_cdp, "status", return_value=report), contextlib.redirect_stdout(out):
            self.assertEqual(xrepost_cdp.main(["--url", "http://127.0.0.1:9222"]), 0)
        self.assertIn("Seguro", out.getvalue())

        report = {"secure": False, "reachable": False, "url": "http://x", "profile": "", "problems": ["fallo"]}
        out = io.StringIO()
        with mock.patch.object(xrepost_cdp, "status", return_value=report), contextlib.redirect_stdout(out):
            self.assertEqual(xrepost_cdp.main(["--json"]), 1)
        self.assertIn("fallo", out.getvalue())


class ScheduleHardeningTest(Base):
    def _future(self, days=1):
        return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=days)).isoformat()

    def test_parse_iso_y_compute_next(self):
        self.assertEqual(xrepost_schedule.parse_iso(self._future()).tzinfo, dt.timezone.utc)
        local = dt.datetime.now().replace(tzinfo=None).isoformat()
        self.assertEqual(xrepost_schedule.parse_iso(local).tzinfo, dt.timezone.utc)
        with self.assertRaises(ValueError):
            xrepost_schedule.parse_iso("")
        with self.assertRaises(ValueError):
            xrepost_schedule.parse_iso("mañana")

        base = dt.datetime(2024, 1, 31, 10, tzinfo=dt.timezone.utc)
        self.assertEqual(
            xrepost_schedule.compute_next({"frequency": "once", "run_at": "2024-02-01T10:00:00Z"}, after=base),
            "2024-02-01T10:00:00Z",
        )
        self.assertEqual(
            xrepost_schedule.compute_next({"frequency": "once", "run_at": "2024-01-01T10:00:00Z"}, after=base),
            "",
        )
        self.assertEqual(
            xrepost_schedule.compute_next({"frequency": "daily", "run_at": "2024-01-30T10:00:00Z"}, after=base),
            "2024-02-01T10:00:00Z",
        )
        self.assertEqual(
            xrepost_schedule.compute_next({"frequency": "weekly", "run_at": "2024-01-25T10:00:00Z"}, after=base),
            "2024-02-01T10:00:00Z",
        )
        self.assertEqual(
            xrepost_schedule.compute_next({"frequency": "monthly", "run_at": "2024-01-31T10:00:00Z"}, after=base),
            "2024-02-29T10:00:00Z",
        )
        self.assertEqual(xrepost_schedule.compute_next({"frequency": "inventada", "run_at": self._future()}), "")
        self.assertEqual(xrepost_schedule.compute_next({"frequency": "daily", "run_at": "roto"}), "")

    def test_crud_y_validaciones(self):
        store = xrepost_schedule.ScheduleStore(self.root / "schedules.json")
        with self.assertRaises(ValueError):
            store.create("", {}, frequency="daily", run_at=self._future())
        with self.assertRaises(ValueError):
            store.create("x", {}, frequency="hourly", run_at=self._future())
        with self.assertRaises(ValueError):
            store.create("x", {}, frequency="daily", run_at="2020-01-01T00:00:00Z")

        item = store.create("diaria", {"users": "@foo", "limit": 2, "ignorado": "x"}, frequency="daily", run_at=self._future())
        self.assertEqual(item["params"]["limit"], 2)
        self.assertNotIn("ignorado", item["params"])
        self.assertEqual(len(store.list()), 1)
        self.assertEqual(store.get(item["id"])["name"], "diaria")
        self.assertIsNone(store.get("no-existe"))

        updated = store.update(item["id"], name="nueva", enabled=False, notify=False, last_run="2024-01-01T00:00:00Z")
        self.assertEqual(updated["name"], "nueva")
        self.assertFalse(updated["enabled"])
        self.assertFalse(updated["notify"])
        self.assertEqual(store.update(item["id"], frequency="weekly")["frequency"], "weekly")
        self.assertEqual(store.update(item["id"], run_at=self._future(2))["run_at"][-1], "Z")
        self.assertEqual(store.update(item["id"], params={"users": "@bar"})["params"]["users"], "@bar")
        self.assertEqual(store.update(item["id"], last_job="job")["last_job"], "job")
        self.assertIsInstance(store.update(item["id"], last_result="ok")["last_result"], str)
        with self.assertRaises(ValueError):
            store.update(item["id"], frequency="hourly")
        with self.assertRaises(ValueError):
            store.update(item["id"], name="  ")
        with self.assertRaises(KeyError):
            store.update("no-existe", name="x")
        with self.assertRaises(ValueError):
            store.update(item["id"], run_at="roto")

        self.assertTrue(store.delete(item["id"]))
        self.assertFalse(store.delete(item["id"]))
        self.assertEqual(store.list(), [])

    def test_due_y_mark_run(self):
        store = xrepost_schedule.ScheduleStore(self.root / "schedules.json")
        item = store.create("diaria", {}, frequency="daily", run_at=self._future())
        self.assertEqual(store.due(), [])

        later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=10)
        self.assertEqual(len(store.due(at=later)), 1)
        store.update(item["id"], enabled=False)
        self.assertEqual(store.due(at=later), [])

        def break_next(data):
            for row in data["schedules"]:
                if row["id"] == item["id"]:
                    row["next_run"] = "roto"
            return data

        store.update(item["id"], enabled=True)
        store.store.mutate(break_next)
        self.assertEqual(store.due(), [])

        marked = store.mark_run(item["id"], job_id="job1", result="ok")
        self.assertEqual(marked["last_job"], "job1")
        self.assertIn("Z", marked["next_run"])
        with self.assertRaises(KeyError):
            store.mark_run("no-existe", job_id="x", result="y")

    def test_limite_de_programaciones(self):
        store = xrepost_schedule.ScheduleStore(self.root / "schedules.json")
        with mock.patch.object(xrepost_schedule, "MAX_SCHEDULES", 1):
            store.create("uno", {}, frequency="once", run_at=self._future())
            with self.assertRaises(ValueError):
                store.create("dos", {}, frequency="once", run_at=self._future())


class SecurityHardeningTest(Base):
    def test_sesiones_expiran_y_se_revocan(self):
        clock = {"value": 1000.0}
        auth = xrepost_security.AuthManager("token-maestro-123", ttl=60, idle=10, max_failures=2, window=60, block=30, clock=lambda: clock["value"])
        session = auth.create("127.0.0.1", "agente")
        self.assertTrue(auth.get(session.sid))
        clock["value"] += 11
        self.assertIsNone(auth.get(session.sid))

        session = auth.create("127.0.0.1")
        rotated = auth.rotate(session.sid, "127.0.0.1")
        self.assertIsNotNone(rotated)
        self.assertIsNone(auth.get(session.sid))
        self.assertEqual(rotated.rotations, 1)
        self.assertIsNone(auth.rotate(None))

        self.assertTrue(auth.revoke(rotated.sid))
        self.assertFalse(auth.revoke(rotated.sid))
        auth.create()
        self.assertGreaterEqual(auth.revoke_all(), 1)

        self.assertTrue(auth.master_ok("token-maestro-123"))
        self.assertFalse(auth.master_ok("otro"))
        self.assertFalse(auth.master_ok(None))
        with self.assertRaises(ValueError):
            xrepost_security.AuthManager("corto")

    def test_fuerza_bruta(self):
        clock = {"value": 100.0}
        auth = xrepost_security.AuthManager("token-maestro-123", max_failures=2, window=60, block=30, clock=lambda: clock["value"])
        self.assertEqual(auth.register_failure("ip"), 0)
        self.assertEqual(auth.register_failure("ip"), 30)
        self.assertEqual(auth.blocked_for("ip"), 30)
        clock["value"] += 31
        self.assertEqual(auth.blocked_for("ip"), 0)
        auth.register_success("ip")

    def test_csrf_cookies_y_utilidades(self):
        auth = xrepost_security.AuthManager("token-maestro-123")
        session = auth.create()
        self.assertTrue(auth.csrf_ok(session, session.csrf))
        self.assertFalse(auth.csrf_ok(session, "mal"))
        self.assertFalse(auth.csrf_ok(None, "x"))
        described = auth.describe(session)
        self.assertTrue(described["authenticated"])
        self.assertFalse(auth.describe(None)["authenticated"])

        header = xrepost_security.cookie_header("sid", secure=True)
        self.assertIn("HttpOnly", header)
        self.assertIn("SameSite=Strict", header)
        self.assertIn("Secure", header)
        self.assertIn("Max-Age=0", xrepost_security.clear_cookie_header())
        self.assertEqual(
            xrepost_security.client_id(type("H", (), {"client_address": ("127.0.0.1", 1)})()),
            "127.0.0.1",
        )
        self.assertEqual(xrepost_security.client_id(object()), "local")

        self.assertTrue(xrepost_security.allowed_origin("", "127.0.0.1:8765"))
        self.assertTrue(xrepost_security.allowed_origin("http://127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(xrepost_security.allowed_origin("https://127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(xrepost_security.allowed_origin("http://user:pass@127.0.0.1:8765", "127.0.0.1:8765"))
        self.assertFalse(xrepost_security.allowed_origin("http://evil.test:8765", "127.0.0.1:8765"))
        self.assertFalse(xrepost_security.allowed_origin("http://127.0.0.1:9999", "127.0.0.1:8765"))

        self.assertTrue(xrepost_security.host_allowed("127.0.0.1:8765", server_port=8765))
        self.assertTrue(xrepost_security.host_allowed("localhost", server_port=8765))
        self.assertFalse(xrepost_security.host_allowed("127.0.0.1:1", server_port=8765))
        self.assertFalse(xrepost_security.host_allowed("evil.test"))
        self.assertFalse(xrepost_security.host_allowed("127.0.0.1:no"))


class ExportFormatsTest(Base):
    def test_formatos_y_proteccion_csv(self):
        rows = [
            {"fecha": "2024-01-01", "autor": "A", "usuario": "@a", "texto": "=SUM(1)", "url": "https://x.com/a/status/1", "estado": "ok"},
            {"fecha": "2024-01-02", "autor": "B", "usuario": "", "texto": "+malo", "url": "", "estado": "fallo"},
        ]
        csv_text = xrepost_exports.rows_to_csv(rows)
        self.assertIn("'=SUM(1)", csv_text)
        self.assertIn("'+malo", csv_text)
        path = self.root / "export.csv"
        self.assertTrue(xrepost_exports.write_csv(rows, path).exists())

        md = xrepost_exports.rows_to_markdown(rows, title="Informe")
        self.assertIn("Informe", md)
        self.assertIn("[post](https://x.com/a/status/1)", md)
        self.assertTrue(xrepost_exports.write_markdown(rows, self.root / "export.md").exists())

        html_text = xrepost_exports.rows_to_html(rows, subtitle="sub")
        self.assertIn("<table", html_text)
        self.assertIn("noopener", html_text)
        self.assertIn("Ver en X", html_text)

        pdf = xrepost_exports.rows_to_pdf(rows, subtitle="sub")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn(b"%%EOF", pdf)
        self.assertTrue(xrepost_exports.write_pdf(rows, self.root / "export.pdf").exists())

        payload = {"a": 1}
        json_path = xrepost_exports.write_json(payload, self.root / "export.json")
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8")), payload)


class HistoryIntegrityTest(Base):
    def test_validate_event_y_lineas_corruptas(self):
        good = {"id": "1", "action": "repost", "result": "reposted", "ts": "2024-01-01T10:00:00Z"}
        self.assertEqual(xrepost_history.validate_event(good), [])
        cases = [
            ("objeto", "objeto"),
            ("id", {"action": "repost", "result": "ok", "ts": "2024-01-01"}),
            ("acción", {"id": "1", "action": "volcar", "result": "ok", "ts": "2024-01-01"}),
            ("result", {"id": "1", "action": "repost", "result": "", "ts": "2024-01-01"}),
            ("ts", {"id": "1", "action": "repost", "result": "ok"}),
            ("ts no ISO", {"id": "1", "action": "repost", "result": "ok", "ts": "ayer"}),
            ("url", {"id": "1", "action": "repost", "result": "ok", "ts": "2024-01-01", "url": 3}),
        ]
        for needle, event in cases:
            problems = xrepost_history.validate_event(event)
            self.assertTrue(any(needle in item for item in problems), (needle, problems))

        path = self.root / "hist.jsonl"
        path.write_bytes(
            b"\xff\xfe linea rota\n"
            + b'{"id": "2", "action": "repost"}\n'
            + b"\n"
            + (json.dumps(good) + "\n").encode("utf-8")
        )
        events = xrepost_history.read_events(path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], "1")
        report = xrepost_history.diagnose(path)
        self.assertEqual(report["corrupt_events"], 2)
        self.assertEqual(report["integrity"], "revisar")

    def test_rotacion_y_append_event(self):
        path = self.root / "hist.jsonl"
        path.write_text("x" * 100, encoding="utf-8")
        event = {"id": "1", "action": "repost", "result": "reposted", "ts": "2024-01-01T10:00:00Z"}
        written = xrepost_history.append_event(path, event, max_bytes=10)
        self.assertEqual(written["id"], "1")
        archives = xrepost_history.archive_paths(path)
        self.assertEqual(len(archives), 1)
        self.assertTrue(archives[0].name.startswith("history-archivo-"))
        self.assertEqual(len(xrepost_history.read_events(path)), 1)

        with self.assertRaises(ValueError):
            xrepost_history.append_event(path, {"id": "", "action": "repost"}, max_bytes=0)

        os.environ["XREPOST_HISTORY_MAX_BYTES"] = "invalido"
        try:
            self.assertEqual(xrepost_history.append_event(path, event)["id"], "1")
        finally:
            os.environ.pop("XREPOST_HISTORY_MAX_BYTES", None)

        self.assertEqual(xrepost_history.history_files(path)[-1], path)
        self.assertEqual(xrepost_history.archive_paths(self.root / "nada" / "h.jsonl"), [])

    def test_backup_verify_list_y_restore_forzado(self):
        path = self.root / "hist.jsonl"
        event = {"id": "1", "action": "repost", "result": "reposted", "ts": "2024-01-01T10:00:00Z"}
        xrepost_history.append_event(path, event)

        backup = xrepost_history.backup(path)
        self.assertEqual(backup["events"], 1)
        self.assertTrue(Path(backup["path"]).exists())

        verified = xrepost_history.verify_backup(backup["path"])
        self.assertTrue(verified["ok"])
        with open(backup["path"], "ab") as fh:
            fh.write(b"x")
        tampered = xrepost_history.verify_backup(backup["path"])
        self.assertFalse(tampered["ok"])

        listing = xrepost_history.list_backups(path)
        self.assertEqual(len(listing), 1)
        self.assertFalse(xrepost_history.list_backups(self.root / "nada" / "hist.jsonl"))

        path.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError):
            xrepost_history.restore(path, backup["path"])  # checksum alterado
        restored = xrepost_history.restore(path, backup["path"], force=True)
        self.assertEqual(restored["diagnostic"]["total_events"], 1)
        with self.assertRaises((ValueError, OSError)):
            xrepost_history.restore(path, self.root / "no-existe.json")

    def test_stats_agregadas(self):
        entries = [
            {"id": "1", "action": "repost", "result": "reposted", "ts": "2024-01-01T10:00:00Z"},
            {"id": "1", "action": "undo", "result": "undone", "ts": "2024-01-02T10:00:00Z"},
            {"id": "2", "action": "repost", "result": "failed", "ts": "2024-01-03T10:00:00Z"},
        ]
        self.assertEqual(xrepost_history.stats(entries)["reposted"], 0)
        self.assertEqual(xrepost_history.stats(entries[:2])["undoable"], 0)
        first = xrepost_history.stats(entries[:1])
        self.assertEqual(first["reposted"], 1)
        self.assertEqual(first["undoable"], 1)


class GroupsAndAccountsTest(Base):
    def test_grupos_crud_y_miembros(self):
        store = xrepost_groups.GroupStore(self.root / "groups.json")
        with self.assertRaises(ValueError):
            store.create("")
        group = store.create("Equipo", "desc", ["@foo", "bar", "foo", "mal handle!"])
        self.assertEqual([m["handle"] for m in group["members"]], ["foo", "bar"])
        with self.assertRaises(ValueError):
            store.create("equipo")

        self.assertEqual(store.get(group["id"])["name"], "Equipo")
        self.assertIsNone(store.get("no-existe"))
        updated = store.update(group["id"], name="Equipo 2", description="otra", members=["@baz"])
        self.assertEqual(updated["name"], "Equipo 2")
        self.assertEqual([m["handle"] for m in updated["members"]], ["baz"])
        with self.assertRaises(ValueError):
            store.update(group["id"], name="  ")
        otro = store.create("Otro")
        with self.assertRaises(ValueError):
            store.update(group["id"], name="otro")
        self.assertTrue(store.delete(otro["id"]))
        with self.assertRaises(KeyError):
            store.update("no-existe", name="x")

        store.add_members(group["id"], ["@otro"])
        self.assertIn("otro", [m["handle"] for m in store.get(group["id"])["members"]])
        store.remove_members(group["id"], ["BAZ"])
        self.assertNotIn("baz", [m["handle"].lower() for m in store.get(group["id"])["members"]])
        with self.assertRaises(KeyError):
            store.add_members("no-existe", ["x"])
        with self.assertRaises(KeyError):
            store.remove_members("no-existe", ["x"])

        self.assertTrue(store.delete(group["id"]))
        self.assertFalse(store.delete(group["id"]))

    def test_importacion_exportacion_csv(self):
        store = xrepost_groups.GroupStore(self.root / "groups.json")
        group = store.create("Equipo")
        text = "handle,alias\n@foo, Foo\nbar;Baz\nfoo,dup\nmal handle!,X\n# comentario\n"
        parsed = store.parse_import(text)
        self.assertEqual([item["handle"] for item in parsed["accounts"]], ["foo", "bar"])
        self.assertEqual(parsed["accounts"][1]["alias"], "Baz")
        self.assertTrue(any(item["reason"] == "duplicado" for item in parsed["skipped"]))
        self.assertTrue(any("no válido" in item["reason"] for item in parsed["skipped"]))

        store.import_into(group["id"], text)
        self.assertEqual(len(store.get(group["id"])["members"]), 2)
        store.import_into(group["id"], "@nuevo", replace=True)
        self.assertEqual([m["handle"] for m in store.get(group["id"])["members"]], ["nuevo"])

        csv_text = store.export_csv(group["id"])
        self.assertIn("nuevo", csv_text)
        self.assertIn("grupo,handle,alias", csv_text)
        store.update(group["id"], members=[{"handle": "x", "alias": "=SUMA(1)"}])
        self.assertIn("'=SUMA(1)", store.export_csv())

        with mock.patch.object(xrepost_groups, "MAX_MEMBERS", 1):
            with self.assertRaises(ValueError):
                store.update(group["id"], members=["a", "b"])

    def test_metadatos_y_estadisticas(self):
        meta = xrepost_groups.AccountMetaStore(self.root / "meta.json")
        item = meta.set("@Foo", alias="Foo", favorite=True)
        self.assertEqual(item["alias"], "Foo")
        self.assertTrue(item["favorite"])
        self.assertEqual(meta.all()["foo"]["handle"], "Foo")
        meta.set("@Foo", alias="Bar")
        self.assertEqual(meta.all()["foo"]["alias"], "Bar")
        with self.assertRaises(ValueError):
            meta.set("mal handle!")
        self.assertTrue(meta.remove("@foo"))
        self.assertFalse(meta.remove("@foo"))
        self.assertEqual(meta.all(), {})

        history = self.root / "hist.jsonl"
        xrepost_history.append_event(history, {"id": "1", "action": "repost", "result": "reposted", "ts": "2024-01-01T00:00:00Z", "search_user": "@foo"})
        xrepost_history.append_event(history, {"id": "2", "action": "repost", "result": "quoted", "ts": "2024-01-02T00:00:00Z", "search_user": "@foo"})
        xrepost_history.append_event(history, {"id": "1", "action": "undo", "result": "undone", "ts": "2024-01-03T00:00:00Z", "search_user": "@foo"})
        xrepost_history.append_event(history, {"id": "3", "action": "repost", "result": "failed", "ts": "2024-01-04T00:00:00Z", "search_user": "@bar"})
        stats = xrepost_groups.account_stats(history)
        by_handle = {row["handle"]: row for row in stats}
        self.assertEqual(by_handle["foo"]["reposts"], 1)
        self.assertEqual(by_handle["foo"]["quotes"], 1)
        self.assertEqual(by_handle["foo"]["undone"], 1)
        self.assertEqual(by_handle["bar"]["errors"], 1)

        self.assertTrue(str(xrepost_groups.default_group_path(self.root / "accounts.json", None)).endswith("groups.json"))
        self.assertTrue(str(xrepost_groups.default_meta_path(self.root / "accounts.json", None)).endswith("accounts_meta.json"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
