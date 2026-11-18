#!/usr/bin/env python3
"""Pruebas del panel web con un motor simulado (sin red ni Chrome)."""

from __future__ import annotations

import csv
import http.client
import json
import os
import shlex
import stat
import tempfile
import textwrap
import threading
import time
import unittest
from pathlib import Path

from app import App, Job, MAX_JOBS, create_server, main, read_history


STUB = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import csv, datetime as dt, json, os, sys, time

    HISTORY = os.environ.get("X_HISTORY", "")
    LIMIT = int(os.environ.get("X_LIMIT", "10"))
    ONLY = os.environ.get("X_ONLY_URLS_FILE", "")
    SLEEP = float(os.environ.get("STUB_SLEEP", "0") or 0)

    def now():
        return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def url_id(url):
        return url.rstrip("/").rsplit("/", 1)[-1]

    def save(action, result, url):
        if not HISTORY:
            return
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        rec = {
            "ts": now(),
            "run": "run-test",
            "action": action,
            "result": result,
            "id": url_id(url),
            "url": url,
            "author": "Autor",
            "handle": "foo",
            "posted_at": "2024-01-01T10:00:00Z",
        }
        with open(HISTORY, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\\n")

    def write(path, rows):
        if not path:
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if path.endswith(".md"):
            lines = ["| Fecha | Autor | Texto | Enlace | Estado |", "|---|---|---|---|---|"]
            for r in rows:
                lines.append(
                    f"| {r['fecha']} | {r['autor']} {r['usuario']} | {r['texto']} | "
                    f"[post]({r['url']}) | {r['estado']} |"
                )
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\\n".join(lines) + "\\n")
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(
                fh, fieldnames=["fecha", "autor", "usuario", "texto", "url", "estado"]
            )
            w.writeheader()
            w.writerows(rows)

    def main():
        dump = os.environ.get("STUB_ENV_DUMP", "")
        if dump:
            with open(dump, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        k: os.environ.get(k, "")
                        for k in (
                            "X_QUOTE", "X_HASHTAGS", "X_APPLY",
                            "X_ONLY_URLS_FILE", "X_UNDO_TARGET", "X_UNDO_N",
                        )
                    },
                    fh,
                )
        if os.environ.get("STUB_FAIL") == "1":
            print("fallo simulado del motor")
            return 3

        args = sys.argv[1:]
        if "--undo" in args:
            url = args[args.index("--undo") + 1]
            time.sleep(SLEEP)
            save("undo", "undone", url)
            print("deshecho:", url)
            return 0
        if "--undo-last" in args:
            n = 0
            idx = args.index("--undo-last")
            if idx + 1 < len(args) and args[idx + 1].isdigit():
                n = int(args[idx + 1])
            entries = []
            try:
                with open(HISTORY, encoding="utf-8") as fh:
                    entries = [json.loads(line) for line in fh if line.strip()]
            except OSError:
                pass
            done = {}
            for e in entries:
                if e.get("action") == "repost" and e.get("result") == "reposted":
                    done[e["id"]] = e
                elif e.get("action") == "undo" and e.get("result") == "undone":
                    done.pop(e.get("id"), None)
            targets = list(done.values())[-n:] if n else list(done.values())
            time.sleep(SLEEP)
            for e in targets:
                save("undo", "undone", e["url"])
                print("deshecho:", e["url"])
            return 0

        csv_path = ""
        md_path = ""
        if "--csv" in args:
            csv_path = args[args.index("--csv") + 1]
        if "--md" in args:
            md_path = args[args.index("--md") + 1]

        selected = []
        if ONLY:
            with open(ONLY, encoding="utf-8") as fh:
                selected = json.load(fh)
        rows = []
        for item in selected:
            rows.append(
                {
                    "fecha": item.get("fecha", "2024-01-01 10:00"),
                    "autor": item.get("autor", "Autor"),
                    "usuario": item.get("usuario", "@foo"),
                    "texto": item.get("texto", "texto"),
                    "url": item.get("url", ""),
                    "estado": "reposteado" if os.environ.get("X_APPLY") == "1" else "solo listado",
                }
            )
        if not ONLY:
            rows = [
                {
                    "fecha": "2024-01-01 10:00",
                    "autor": "Autor",
                    "usuario": "@foo",
                    "texto": "primer post",
                    "url": "https://x.com/foo/status/1",
                    "estado": "solo listado",
                },
                {
                    "fecha": "2024-01-02 11:30",
                    "autor": "Otra",
                    "usuario": "@bar",
                    "texto": "segundo post",
                    "url": "https://x.com/bar/status/2",
                    "estado": "solo listado",
                },
            ]

        if os.environ.get("X_APPLY") == "1":
            pending = [dict(row, estado="pendiente") for row in rows]
            write(csv_path, pending)
            write(md_path, pending)
            time.sleep(SLEEP)
            done = 0
            for row in rows:
                if done >= LIMIT:
                    break
                save("repost", "reposted", row["url"])
                done += 1
                print("  reposteado:", row["url"])
                time.sleep(max(0.0, SLEEP / 4))
            write(csv_path, rows)
            write(md_path, rows)
            print("Total reposteado:", done)
            return 0

        time.sleep(SLEEP)
        write(csv_path, rows)
        write(md_path, rows)
        print("DRY-RUN:", len(rows), "posts")
        return 0

    sys.exit(main())
    '''
)


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xrepost-web-test-")
        self.root = Path(self.tmp.name)
        self.engine = self.root / "engine.py"
        self.engine.write_text(STUB, encoding="utf-8")
        self.engine.chmod(self.engine.stat().st_mode | stat.S_IXUSR)
        self.history = self.root / "history.jsonl"
        self.runs = self.root / "runs"
        self.token = "token-de-prueba"
        self.app = App(
            engine=self.engine,
            history=self.history,
            runs=self.runs,
            token=self.token,
        )
        self.httpd = create_server(self.app, 0)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.saved_env = {}
        self.set_env("XREPOST_NETWORK_CONFIG", str(self.root / "network.json"))

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self.tmp.cleanup()

    def set_env(self, key, value):
        if key not in self.saved_env:
            self.saved_env[key] = os.environ.get(key)
        os.environ[key] = value

    def request(self, method, path, body=None, *, token=True, headers=None, origin=None):
        hdrs = dict(headers or {})
        if token:
            hdrs["X-Token"] = self.token
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        if origin:
            hdrs["Origin"] = origin
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(method, path, body=data, headers=hdrs)
            resp = conn.getresponse()
            payload = resp.read()
            return resp.status, dict(resp.getheaders()), payload
        finally:
            conn.close()

    def json_request(self, method, path, body=None, **kwargs):
        status, headers, payload = self.request(method, path, body, **kwargs)
        data = json.loads(payload.decode("utf-8")) if payload else None
        return status, headers, data

    def wait_job(self, job_id, timeout=12):
        deadline = time.time() + timeout
        while time.time() < deadline:
            status, _, job = self.json_request("GET", f"/api/jobs/{job_id}")
            self.assertEqual(status, 200, job)
            if job["status"] != "running":
                return job
            time.sleep(0.05)
        self.fail(f"la ejecución {job_id} no terminó a tiempo")

    def params(self, **overrides):
        data = {
            "users": "@foo,bar",
            "from": "2024-01-01",
            "to": "2024-01-31",
            "scope": "originals",
            "limit": 10,
            "delay": 20,
            "match": "",
            "exclude": "",
        }
        data.update(overrides)
        return data

    def preview(self, **overrides):
        status, _, data = self.json_request("POST", "/api/preview", self.params(**overrides))
        self.assertEqual(status, 202, data)
        return self.wait_job(data["id"])

    def apply(self, preview, **overrides):
        body = self.params(**overrides)
        body.update({"preview_id": preview["id"], "confirm": True})
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 202, data)
        return self.wait_job(data["id"])

    # --- autenticación y seguridad -------------------------------------

    def test_main_refuses_non_loopback_host(self):
        self.assertEqual(main(["--host", "0.0.0.0", "--no-open"]), 2)

    def test_health_requires_token(self):
        status, _, data = self.json_request("GET", "/api/health", token=False)
        self.assertEqual(status, 401)
        self.assertIn("error", data)

        status, _, health = self.json_request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["ok"])
        self.assertTrue(health["engine_ok"])
        self.assertEqual(health["history"], str(self.history))
        self.assertFalse(health["busy"])

    def test_index_token_sets_cookie_and_serves_panel(self):
        status, headers, _ = self.request("GET", "/?token=malo", token=False)
        self.assertEqual(status, 401)

        status, headers, payload = self.request("GET", f"/?token={self.token}", token=False)
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "/")
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("xrepost_token=", cookie)
        self.assertIn("HttpOnly", cookie)

        status, headers, page = self.request(
            "GET", "/", token=False, headers={"Cookie": f"xrepost_token={self.token}"}
        )
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn("xrepost", page.decode("utf-8"))

    def test_static_files_need_token_and_block_traversal(self):
        status, _, _ = self.request("GET", "/static/app.js", token=False)
        self.assertEqual(status, 401)

        status, headers, payload = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("Content-Type", ""))
        self.assertIn(b"use strict", payload)

        status, _, _ = self.request("GET", "/static/%2e%2e/app.py")
        self.assertEqual(status, 404)

    def test_host_origin_and_content_type_checks(self):
        status, _, _ = self.request(
            "GET", "/api/health", headers={"Host": "evil.example"}
        )
        self.assertEqual(status, 403)

        status, _, _ = self.request(
            "POST", "/api/preview", self.params(), origin="http://evil.example"
        )
        self.assertEqual(status, 403)

        status, _, _ = self.request(
            "POST",
            "/api/preview",
            token=False,
            headers={"Content-Type": "text/plain", "X-Token": self.token},
        )
        self.assertEqual(status, 415)

    # --- previsualización y exportaciones ------------------------------

    def test_preview_generates_posts_and_exports(self):
        job = self.preview()
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["kind"], "preview")
        self.assertEqual(len(job["posts"]), 2)
        self.assertEqual(job["posts"][0]["url"], "https://x.com/foo/status/1")
        self.assertNotIn("key", job["params"])
        self.assertTrue(job["exports"]["csv"])
        self.assertTrue(job["exports"]["md"])

        status, headers, csv_body = self.request("GET", f"/api/jobs/{job['id']}/export/csv")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        rows = list(csv.DictReader(csv_body.decode("utf-8").splitlines()))
        self.assertEqual([row["url"] for row in rows], [p["url"] for p in job["posts"]])

        status, _, md_body = self.request("GET", f"/api/jobs/{job['id']}/export/md")
        self.assertEqual(status, 200)
        self.assertIn(b"| Fecha |", md_body)
        self.assertFalse(self.history.exists())

    def test_preview_accepts_dd_mm_yyyy(self):
        job = self.preview(**{"from": "01/02/2024", "to": "29/02/2024"})
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["params"]["from"], "2024-02-01")
        self.assertEqual(job["params"]["to"], "2024-02-29")

    def test_preview_validation_errors(self):
        cases = [
            {"users": ""},
            {"users": "mal-handle"},
            {"users": ",".join(f"u{i}" for i in range(11))},
            {"from": "31/02/2024"},
            {"from": "2024-02-30"},
            {"from": "2024-03-01", "to": "2024-02-01"},
            {"scope": "otro"},
            {"limit": 0},
            {"limit": 51},
            {"delay": -1},
            {"match": "x" * 201},
            {"quote": "!!!"},
            {"quote": "#"},
            {"quote": " ".join(chr(ord("a") + i) * 50 for i in range(6))},
        ]
        for case in cases:
            with self.subTest(case=case):
                status, _, data = self.json_request(
                    "POST", "/api/preview", self.params(**case)
                )
                self.assertEqual(status, 400, data)
                self.assertTrue(data["error"])

    def test_accounts_endpoint_requires_token_and_suggests_used(self):
        status, _, _ = self.request("GET", "/api/accounts?q=ete", token=False)
        self.assertEqual(status, 401)

        self.app.record_accounts("@ETECSA_Cuba, ana, luis")
        self.assertTrue(self.app.accounts.exists())
        self.assertEqual(self.app.accounts.parent, self.history.parent)

        status, _, data = self.json_request("GET", "/api/accounts?q=ete")
        self.assertEqual(status, 200)
        self.assertEqual([item["handle"] for item in data["accounts"]], ["ETECSA_Cuba"])

        status, _, data = self.json_request("GET", "/api/accounts?q=et&exclude=ETECSA_Cuba")
        self.assertEqual(status, 200)
        self.assertEqual(data["accounts"], [])

        status, _, data = self.json_request("GET", "/api/accounts?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["accounts"]), 2)

    def test_preview_records_accounts_for_autocomplete(self):
        self.preview(users="@nueva_cuenta, otra_cuenta")
        status, _, data = self.json_request("GET", "/api/accounts?q=nueva")
        self.assertEqual(status, 200)
        self.assertEqual([item["handle"] for item in data["accounts"]], ["nueva_cuenta"])

        status, _, data = self.json_request("GET", "/api/accounts?q=otra")
        self.assertEqual([item["handle"] for item in data["accounts"]], ["otra_cuenta"])

    def test_hashtags_endpoint_requires_token_and_suggests_used(self):
        status, _, _ = self.request("GET", "/api/hashtags?q=ete", token=False)
        self.assertEqual(status, 401)

        self.app.record_hashtags("#ETECSA #Cuba, etecsa")
        self.assertTrue(self.app.hashtags.exists())
        self.assertEqual(self.app.hashtags.parent, self.history.parent)

        status, _, data = self.json_request("GET", "/api/hashtags?q=ete")
        self.assertEqual(status, 200)
        self.assertEqual([item["tag"] for item in data["hashtags"]], ["ETECSA"])

        status, _, data = self.json_request("GET", "/api/hashtags?q=c&exclude=ETECSA")
        self.assertEqual(status, 200)
        self.assertEqual([item["tag"] for item in data["hashtags"]], ["Cuba"])

        status, _, data = self.json_request("GET", "/api/hashtags?limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["hashtags"]), 1)

    def test_clear_accounts_requires_token_and_ignores_history(self):
        status, _, _ = self.request("POST", "/api/accounts/clear", {}, token=False)
        self.assertEqual(status, 401)

        self.history.write_text(
            json.dumps({"ts": "2020-01-01T00:00:00Z", "action": "repost", "search_user": "Vieja"}) + "\n",
            encoding="utf-8",
        )
        self.app.record_accounts("@Otra")
        status, _, data = self.json_request("GET", "/api/accounts?q=")
        self.assertEqual(status, 200)
        self.assertEqual({item["handle"] for item in data["accounts"]}, {"Vieja", "Otra"})

        status, _, data = self.json_request("POST", "/api/accounts/clear", {})
        self.assertEqual(status, 200, data)
        self.assertTrue(data["ok"])

        status, _, data = self.json_request("GET", "/api/accounts?q=")
        self.assertEqual(status, 200)
        self.assertEqual(data["accounts"], [])

        # Lo usado después del borrado vuelve a sugerirse; lo viejo no.
        self.app.record_accounts("@Nueva")
        status, _, data = self.json_request("GET", "/api/accounts?q=")
        self.assertEqual([item["handle"] for item in data["accounts"]], ["Nueva"])

    def test_clear_hashtags_requires_token_and_removes_suggestions(self):
        status, _, _ = self.request("POST", "/api/hashtags/clear", {}, token=False)
        self.assertEqual(status, 401)

        self.app.record_hashtags("#ETECSA #Cuba")
        status, _, data = self.json_request("GET", "/api/hashtags?q=")
        self.assertEqual({item["tag"] for item in data["hashtags"]}, {"ETECSA", "Cuba"})

        status, _, data = self.json_request("POST", "/api/hashtags/clear", {})
        self.assertEqual(status, 200, data)
        self.assertTrue(data["ok"])

        status, _, data = self.json_request("GET", "/api/hashtags?q=")
        self.assertEqual(status, 200)
        self.assertEqual(data["hashtags"], [])

        self.app.record_hashtags("#Nuevo")
        status, _, data = self.json_request("GET", "/api/hashtags?q=nue")
        self.assertEqual([item["tag"] for item in data["hashtags"]], ["Nuevo"])

    def test_preview_records_hashtags_for_autocomplete(self):
        job = self.preview(quote="ETECSA, cuba")
        self.assertEqual(job["params"]["quote"], "#ETECSA #cuba")

        status, _, data = self.json_request("GET", "/api/hashtags?q=cub")
        self.assertEqual(status, 200)
        self.assertEqual([item["tag"] for item in data["hashtags"]], ["cuba"])

    def test_preview_passes_quote_to_engine(self):
        dump = self.root / "env.json"
        self.set_env("STUB_ENV_DUMP", str(dump))
        job = self.preview(quote="#ETECSA")
        self.assertEqual(job["status"], "done")
        env = json.loads(dump.read_text(encoding="utf-8"))
        self.assertEqual(env["X_QUOTE"], "#ETECSA")
        self.assertEqual(env["X_HASHTAGS"], str(self.app.hashtags))
        self.assertEqual(env["X_APPLY"], "0")

    def test_server_env_does_not_leak_into_jobs(self):
        dump = self.root / "env.json"
        self.set_env("STUB_ENV_DUMP", str(dump))
        self.set_env("X_ONLY_URLS_FILE", str(self.root / "viejo.json"))
        self.set_env("X_QUOTE", "#heredado")
        self.set_env("X_UNDO_TARGET", "999")
        self.set_env("X_UNDO_N", "7")
        job = self.preview()
        self.assertEqual(job["status"], "done")
        self.assertEqual(len(job["posts"]), 2)  # no redirigido a un listado viejo
        env = json.loads(dump.read_text(encoding="utf-8"))
        self.assertEqual(env["X_ONLY_URLS_FILE"], "")
        self.assertEqual(env["X_QUOTE"], "")
        self.assertEqual(env["X_UNDO_TARGET"], "")
        self.assertEqual(env["X_UNDO_N"], "")

    def test_undoable_survives_failed_undo(self):
        url = "https://x.com/foo/status/11"
        events = [
            {"ts": "2026-11-17T10:00:00Z", "run": "r1", "action": "repost",
             "result": "reposted", "id": "11", "url": url},
            {"ts": "2026-11-17T10:05:00Z", "run": "r2", "action": "undo",
             "result": "undo_failed", "id": "11", "url": url},
        ]
        self.history.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
        status, _, data = self.json_request("GET", "/api/history")
        self.assertEqual(status, 200)
        self.assertTrue(data["entries"][0]["undoable"])

        events.append({"ts": "2026-11-17T10:10:00Z", "run": "r3", "action": "undo",
                       "result": "undone", "id": "11", "url": url})
        self.history.write_text(
            "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
        )
        status, _, data = self.json_request("GET", "/api/history")
        self.assertEqual(status, 200)
        self.assertFalse(data["entries"][0]["undoable"])

    def test_keep_alive_survives_rejected_post(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "POST", "/api/preview", body=b"x" * 50,
                headers={"Content-Type": "text/plain", "X-Token": self.token},
            )
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 415)
            # El cuerpo rechazado se drena: la misma conexión sirve la siguiente.
            conn.request("GET", "/api/health", headers={"X-Token": self.token})
            resp = conn.getresponse()
            payload = resp.read()
            self.assertEqual(resp.status, 200)
            self.assertTrue(json.loads(payload)["ok"])
        finally:
            conn.close()

    def test_early_rejection_closes_connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request(
                "POST", "/api/preview", body=b"x" * 50,
                headers={"Content-Type": "application/json"},  # sin token
            )
            resp = conn.getresponse()
            resp.read()
            self.assertEqual(resp.status, 401)
            self.assertEqual(resp.getheader("Connection"), "close")
        finally:
            conn.close()

    def test_unknown_job_and_export(self):
        status, _, _ = self.request("GET", "/api/jobs/deadbeef")
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", "/api/jobs/deadbeef/export/csv")
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", "/api/nope")
        self.assertEqual(status, 404)

    # --- aplicar -------------------------------------------------------

    def test_apply_requires_confirmation_preview_and_minimum_delay(self):
        preview = self.preview()

        body = self.params()
        body["preview_id"] = preview["id"]
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 400)
        self.assertIn("confirmación", data["error"])

        body["confirm"] = True
        body["delay"] = 1
        status, _, _ = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 400)

        body["delay"] = 20
        body["preview_id"] = "nope"
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 400)
        self.assertIn("previsualizar", data["error"])

        body["preview_id"] = preview["id"]
        body["users"] = "@otra"
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 400)
        self.assertIn("cambiaron", data["error"])

    def test_apply_uses_exact_preview_list_and_records_history(self):
        preview = self.preview()
        job = self.apply(preview)
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["kind"], "apply")
        self.assertEqual(
            [p["url"] for p in job["posts"]], [p["url"] for p in preview["posts"]]
        )
        self.assertTrue(all(p["estado"] == "reposteado" for p in job["posts"]))
        self.assertNotIn("only_urls_file", job["params"])
        self.assertTrue((preview["posts"][0]["url"]).startswith("https://x.com/"))

        selected = self.runs / preview["id"] / "selected.json"
        self.assertTrue(selected.exists())
        self.assertEqual(
            [item["url"] for item in json.loads(selected.read_text("utf-8"))],
            [p["url"] for p in preview["posts"]],
        )

        lines = [json.loads(line) for line in self.history.read_text("utf-8").splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(e["action"] == "repost" and e["result"] == "reposted" for e in lines))

        status, _, history = self.json_request("GET", "/api/history?n=10")
        self.assertEqual(status, 200)
        self.assertEqual(len(history["entries"]), 2)
        self.assertTrue(all(entry["undoable"] for entry in history["entries"]))
        self.assertEqual(history["entries"][0]["result_label"], "reposteado")

    def test_apply_records_stub_failure(self):
        preview = self.preview()
        self.set_env("STUB_FAIL", "1")
        body = self.params()
        body.update({"preview_id": preview["id"], "confirm": True})
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 202, data)
        job = self.wait_job(data["id"])
        self.assertEqual(job["status"], "error")
        self.assertIn("código 3", job["error"])
        self.assertFalse(self.history.exists())

    def test_apply_only_selected_posts(self):
        preview = self.preview()
        chosen_url = preview["posts"][1]["url"]
        job = self.apply(preview, selected_urls=[chosen_url])
        self.assertEqual(job["status"], "done")
        self.assertEqual([p["url"] for p in job["posts"]], [chosen_url])

        selected = self.runs / preview["id"] / "selected.json"
        self.assertEqual(
            [item["url"] for item in json.loads(selected.read_text("utf-8"))],
            [chosen_url],
        )
        lines = [json.loads(line) for line in self.history.read_text("utf-8").splitlines()]
        self.assertEqual([e["url"] for e in lines], [chosen_url])

    def test_apply_selection_validation(self):
        preview = self.preview()
        cases = [
            ([], "al menos una"),
            (["https://x.com/foo/status/999"], "no están en la previsualización"),
            ("https://x.com/foo/status/1", "no es válida"),
            ([123], "no es válida"),
        ]
        for selection, message in cases:
            with self.subTest(selection=selection):
                body = self.params()
                body.update(
                    {"preview_id": preview["id"], "confirm": True, "selected_urls": selection}
                )
                status, _, data = self.json_request("POST", "/api/apply", body)
                self.assertEqual(status, 400, data)
                self.assertIn(message, data["error"])
        self.assertFalse(self.history.exists())

    def test_apply_reports_live_progress(self):
        preview = self.preview()
        self.set_env("STUB_SLEEP", "4")
        body = self.params()
        body.update({"preview_id": preview["id"], "confirm": True})
        status, _, data = self.json_request("POST", "/api/apply", body)
        self.assertEqual(status, 202, data)
        job_id = data["id"]

        seen_partial = False
        deadline = time.time() + 12
        while time.time() < deadline:
            _, _, job = self.json_request("GET", f"/api/jobs/{job_id}")
            if job["status"] != "running":
                break
            progress = job.get("progress")
            if progress and progress["total"] == 2 and progress["done"] == 1:
                seen_partial = True
                self.assertEqual(
                    [p["estado"] for p in job["posts"]], ["reposteado", "pendiente"]
                )
                break
            time.sleep(0.05)
        job = self.wait_job(job_id)
        self.assertEqual(job["status"], "done")
        self.assertTrue(seen_partial, "no se observó el progreso parcial en vivo")
        self.assertEqual(job["progress"], {"done": 2, "total": 2})
        self.assertTrue(all(p["estado"] == "reposteado" for p in job["posts"]))

    # --- una ejecución a la vez y cancelación --------------------------

    def test_only_one_job_and_cancel(self):
        self.set_env("STUB_SLEEP", "3")
        status, _, data = self.json_request("POST", "/api/preview", self.params())
        self.assertEqual(status, 202)
        first = data["id"]

        deadline = time.time() + 3
        while time.time() < deadline:
            current = self.app.current
            if current and current.id == first and current.proc is not None:
                break
            time.sleep(0.05)
        else:
            self.fail("el motor simulado no llegó a arrancar")

        status, _, data = self.json_request("POST", "/api/preview", self.params())
        self.assertEqual(status, 409)
        self.assertIn("en curso", data["error"])

        status, _, data = self.json_request("POST", "/api/cancel", {})
        self.assertEqual(status, 200)
        self.assertTrue(data["cancelled"])
        job = self.wait_job(first)
        self.assertEqual(job["status"], "cancelled")

        os.environ.pop("STUB_SLEEP", None)
        self.saved_env.pop("STUB_SLEEP", None)
        job = self.preview()
        self.assertEqual(job["status"], "done")

    # --- deshacer e historial ------------------------------------------

    def test_undo_single_and_last(self):
        preview = self.preview()
        self.apply(preview)

        status, _, data = self.json_request(
            "POST", "/api/undo", {"mode": "url", "url": "https://evil.example/status/1"}
        )
        self.assertEqual(status, 400)

        status, _, data = self.json_request(
            "POST", "/api/undo", {"mode": "url", "url": "https://x.com/foo/status/1"}
        )
        self.assertEqual(status, 202)
        job = self.wait_job(data["id"])
        self.assertEqual(job["status"], "done")

        _, _, history = self.json_request("GET", "/api/history?n=10")
        by_id = {entry["id"]: entry for entry in history["entries"]}
        self.assertEqual(by_id["1"]["action"], "undo")
        self.assertFalse(by_id["1"]["undoable"])
        self.assertTrue(by_id["2"]["undoable"])

        status, _, data = self.json_request("POST", "/api/undo", {"mode": "last"})
        self.assertEqual(status, 202)
        self.wait_job(data["id"])
        _, _, history = self.json_request("GET", "/api/history?n=10")
        by_id = {entry["id"]: entry for entry in history["entries"]}
        self.assertFalse(by_id["2"]["undoable"])
        self.assertEqual(by_id["2"]["result_label"], "deshecho")

        for bad in ({"mode": "otro"}, {"mode": "last", "n": 51}, {"mode": "last", "n": "x"}):
            status, _, _ = self.json_request("POST", "/api/undo", bad)
            self.assertEqual(status, 400)

    def test_history_labels_include_quote_results(self):
        path = self.root / "quote-history.jsonl"
        events = [
            {"id": "5", "ts": "2024-01-01T10:00:00Z", "action": "repost", "result": "quoted", "url": "https://x.com/a/status/5"},
            {"id": "6", "ts": "2024-01-01T10:01:00Z", "action": "repost", "result": "no_composer", "url": "https://x.com/a/status/6"},
        ]
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        labels = {entry["id"]: entry["result_label"] for entry in read_history(path, 10)}
        self.assertEqual(labels["5"], "citado con comentario")
        self.assertEqual(labels["6"], "no se abrió el editor de la cita")

    def test_history_keeps_only_latest_state_per_post(self):
        path = self.root / "manual-history.jsonl"
        events = [
            {"id": "1", "ts": "2024-01-01T10:00:00Z", "action": "repost", "result": "reposted", "url": "https://x.com/a/status/1"},
            {"id": "2", "ts": "2024-01-01T10:01:00Z", "action": "repost", "result": "reposted", "url": "https://x.com/b/status/2"},
            {"id": "1", "ts": "2024-01-01T10:02:00Z", "action": "undo", "result": "undone", "url": "https://x.com/a/status/1"},
        ]
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        entries = read_history(path, 10)
        self.assertEqual([e["id"] for e in entries], ["1", "2"])
        self.assertEqual(entries[0]["action"], "undo")
        self.assertFalse(entries[0]["undoable"])
        self.assertTrue(entries[1]["undoable"])
        self.assertEqual(entries[0]["result_label"], "deshecho")

    def test_history_exposes_quote_and_run(self):
        path = self.root / "quote-run-history.jsonl"
        events = [
            {"id": "7", "ts": "2024-01-01T10:00:00Z", "run": "tanda-1", "action": "repost",
             "result": "quoted", "url": "https://x.com/a/status/7", "quote": "#ETECSA #cuba"},
            {"id": "8", "ts": "2024-01-01T10:01:00Z", "run": "tanda-1", "action": "repost",
             "result": "reposted", "url": "https://x.com/a/status/8"},
        ]
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        entries = read_history(path, 10)
        self.assertEqual([e["id"] for e in entries], ["8", "7"])
        self.assertEqual(entries[0]["quote"], "")
        self.assertEqual(entries[1]["quote"], "#ETECSA #cuba")
        self.assertTrue(all(e["run"] == "tanda-1" for e in entries))

    def test_network_get_muestra_modo_y_flags(self):
        status, _, body = self.json_request("GET", "/api/network")
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "direct")
        self.assertIn("--no-proxy-server", body["flags"])
        self.assertEqual(set(body["modes"]), {"direct", "pac", "auto", "server"})

    def test_network_set_valido_e_invalido(self):
        status, _, body = self.json_request(
            "POST", "/api/network", {"mode": "pac"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["mode"], "pac")
        self.assertTrue(body["flags"][0].startswith("--proxy-pac-url=file:///"))

        status, _, body = self.json_request(
            "POST", "/api/network", {"mode": "server", "proxy": ""}
        )
        self.assertEqual(status, 400)
        self.assertIn("proxy", body["error"].lower())

    def test_network_restart_llama_al_lanzador_con_force(self):
        import app as app_module

        marker = self.root / "restart.args"
        stub = self.root / "fake-chrome.sh"
        stub.write_text(
            "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > "
            + shlex.quote(str(marker))
            + "\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        original = app_module.CHROME_LAUNCHER
        app_module.CHROME_LAUNCHER = stub
        try:
            status, _, body = self.json_request(
                "POST", "/api/network/restart", {}
            )
        finally:
            app_module.CHROME_LAUNCHER = original

        self.assertEqual(status, 200, body)
        self.assertTrue(body["success"])
        self.assertEqual(marker.read_text(encoding="utf-8").strip(), "--force")

    def test_network_restart_bloqueado_con_job_en_curso(self):
        import app as app_module
        from app import Job

        marker = self.root / "restart-no-debia-llamarse"
        stub = self.root / "fake-chrome-fail.sh"
        stub.write_text(
            "#!/usr/bin/env bash\ntouch " + shlex.quote(str(marker)) + "\n",
            encoding="utf-8",
        )
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        original = app_module.CHROME_LAUNCHER
        app_module.CHROME_LAUNCHER = stub
        job = Job("preview", {}, self.app.runs)
        job.status = "running"
        self.app.current = job
        try:
            status, _, body = self.json_request(
                "POST", "/api/network/restart", {}
            )
        finally:
            app_module.CHROME_LAUNCHER = original
            self.app.current = None

        self.assertEqual(status, 409)
        self.assertIn("ejecución", body["error"].lower())
        self.assertFalse(marker.exists())

    def test_500_no_filtra_detalle_interno(self):
        import app as app_module

        original = app_module.read_history
        secreto = "/ruta/secreta/no-filtrar"

        def explota(*args, **kwargs):
            raise RuntimeError(secreto)

        app_module.read_history = explota
        try:
            status, _, body = self.json_request("GET", "/api/history")
        finally:
            app_module.read_history = original

        self.assertEqual(status, 500)
        self.assertNotIn(secreto, json.dumps(body))
        self.assertIn("Error interno del servidor", body["error"])

    def test_prune_jobs_mantiene_ultimos_y_sus_directorios(self):
        creados = []
        for i in range(MAX_JOBS + 5):
            job = Job("preview", {}, self.app.runs)
            job.started += i
            job.dir.mkdir(parents=True)
            (job.dir / "posts.csv").write_text("x", encoding="utf-8")
            self.app.jobs[job.id] = job
            creados.append(job)

        self.app._prune_jobs()

        self.assertEqual(len(self.app.jobs), MAX_JOBS)
        for job in creados[:-MAX_JOBS]:
            self.assertNotIn(job.id, self.app.jobs)
            self.assertFalse(job.dir.exists())
        for job in creados[-MAX_JOBS:]:
            self.assertIn(job.id, self.app.jobs)
            self.assertTrue(job.dir.exists())

    def test_prune_borra_directorios_huerfanos_de_sesiones_anteriores(self):
        huerfanos = []
        for i in range(MAX_JOBS + 2):
            path = self.app.runs / f"huerfano-{i:02d}"
            path.mkdir(parents=True)
            huerfanos.append(path)

        self.app._prune_jobs()

        supervivientes = [p for p in huerfanos if p.exists()]
        self.assertEqual(len(supervivientes), MAX_JOBS)

    def test_prune_no_toca_job_en_curso_ni_su_previsualizacion(self):
        creados = []
        for _ in range(MAX_JOBS + 2):
            job = Job("preview", {}, self.app.runs)
            job.dir.mkdir(parents=True)
            self.app.jobs[job.id] = job
            creados.append(job)
        actual, preview = creados[0], creados[1]
        self.app.current = actual
        actual.params["preview_id"] = preview.id

        self.app._prune_jobs()

        for job in (actual, preview):
            self.assertIn(job.id, self.app.jobs)
            self.assertTrue(job.dir.exists())
        # Los dos protegidos se suman a los 20 más recientes.
        self.assertEqual(len(self.app.jobs), MAX_JOBS + 2)


    # --- sesión, CSRF y UI ---------------------------------------------

    def _session_cookie(self):
        status, headers, data = self.json_request("GET", "/api/session")
        self.assertEqual(status, 200, data)
        cookie = headers.get("Set-Cookie", "")
        self.assertIn("xrepost_sid=", cookie)
        sid = cookie.split("xrepost_sid=", 1)[1].split(";", 1)[0]
        return sid, data

    def test_session_cookie_writes_require_csrf(self):
        sid, data = self._session_cookie()
        self.assertTrue(data["authenticated"])
        self.assertTrue(data["csrf"])
        cookie = {"Cookie": f"xrepost_sid={sid}"}

        status, _, body = self.json_request(
            "POST", "/api/preview", self.params(), token=False, headers=cookie
        )
        self.assertEqual(status, 403)
        self.assertIn("CSRF", body["error"])

        status, _, body = self.json_request(
            "POST",
            "/api/preview",
            self.params(),
            token=False,
            headers={**cookie, "X-CSRF-Token": data["csrf"]},
        )
        self.assertEqual(status, 202, body)

    def test_legacy_cookie_cannot_write_without_csrf(self):
        status, _, body = self.json_request(
            "POST",
            "/api/preview",
            self.params(),
            token=False,
            headers={"Cookie": f"xrepost_token={self.token}"},
        )
        self.assertEqual(status, 403)
        self.assertIn("CSRF", body["error"])

    def test_session_rotate_and_logout(self):
        sid, data = self._session_cookie()
        cookie = {"Cookie": f"xrepost_sid={sid}", "X-CSRF-Token": data["csrf"]}
        status, headers, rotated = self.json_request(
            "POST", "/api/session/rotate", {}, token=False, headers=cookie
        )
        self.assertEqual(status, 200, rotated)
        self.assertNotEqual(rotated["csrf"], data["csrf"])
        new_cookie = headers.get("Set-Cookie", "")
        self.assertIn("xrepost_sid=", new_cookie)
        new_sid = new_cookie.split("xrepost_sid=", 1)[1].split(";", 1)[0]

        status, _, logged = self.json_request(
            "POST",
            "/api/session/logout",
            {},
            token=False,
            headers={"Cookie": f"xrepost_sid={new_sid}", "X-CSRF-Token": rotated["csrf"]},
        )
        self.assertEqual(status, 200, logged)
        self.assertTrue(logged["ok"])
        status, _, _ = self.json_request(
            "GET", "/api/health", token=False, headers={"Cookie": f"xrepost_sid={new_sid}"}
        )
        self.assertEqual(status, 401)

    def test_ui_exposes_tabs_and_sends_csrf(self):
        status, _, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        html = page.decode("utf-8")
        self.assertIn('role="tablist"', html)
        self.assertIn('id="panel-inbox"', html)
        self.assertIn('id="panel-stats"', html)
        self.assertIn("skip-link", html)

        status, _, script = self.request("GET", "/static/app.js")
        self.assertEqual(status, 200)
        js = script.decode("utf-8")
        self.assertIn("X-CSRF-Token", js)
        self.assertIn("/api/session", js)
        self.assertNotIn("localStorage.setItem(\"xrepost.token", js)

        status, _, css = self.request("GET", "/static/styles.css")
        self.assertEqual(status, 200)
        sheet = css.decode("utf-8")
        self.assertIn("[data-theme=\"light\"]", sheet)
        self.assertIn("prefers-reduced-motion", sheet)
        self.assertIn("@media (max-width: 720px)", sheet)

    def test_accounts_all_includes_meta_and_activity(self):
        self.preview()
        status, _, data = self.json_request("POST", "/api/accounts/meta", {
            "handle": "foo", "alias": "Medio", "favorite": True,
        })
        self.assertEqual(status, 200, data)
        status, _, listing = self.json_request("GET", "/api/accounts/all")
        self.assertEqual(status, 200, listing)
        foo = next(item for item in listing["accounts"] if item["handle"] == "foo")
        self.assertEqual(foo["alias"], "Medio")
        self.assertTrue(foo["favorite"])

    def test_groups_crud_members_and_export(self):
        status, _, created = self.json_request("POST", "/api/groups", {
            "name": "Medios", "description": "prueba", "members": ["@foo", "bar"],
        })
        self.assertEqual(status, 201, created)
        group = created["group"]
        self.assertEqual([m["handle"] for m in group["members"]], ["foo", "bar"])

        status, _, listing = self.json_request("GET", "/api/groups")
        self.assertEqual(status, 200, listing)
        self.assertEqual(listing["counts"][group["id"]], 2)

        status, _, added = self.json_request(
            "POST", f"/api/groups/{group['id']}/members", {"handles": ["baz"]}
        )
        self.assertEqual(status, 200, added)
        self.assertIn("baz", [m["handle"] for m in added["group"]["members"]])

        status, _, removed = self.json_request(
            "POST", f"/api/groups/{group['id']}/members",
            {"handles": ["baz"], "action": "remove"},
        )
        self.assertEqual(status, 200, removed)
        self.assertNotIn("baz", [m["handle"] for m in removed["group"]["members"]])

        status, headers, body = self.request("GET", f"/api/groups/{group['id']}/export")
        self.assertEqual(status, 200)
        self.assertIn("text/csv", headers.get("Content-Type", ""))
        self.assertIn(b"foo", body)

        status, _, deleted = self.json_request(
            "POST", f"/api/groups/{group['id']}/delete", {}
        )
        self.assertEqual(status, 200, deleted)
        self.assertTrue(deleted["deleted"])

    def test_profiles_crud_validation_and_run(self):
        status, _, invalid = self.json_request(
            "POST", "/api/filters/validate", {"filters": {"regex": "("}}
        )
        self.assertEqual(status, 400, invalid)

        status, _, ok = self.json_request(
            "POST", "/api/filters/validate", {"filters": {"include": ["cuba"]}}
        )
        self.assertEqual(status, 200, ok)
        self.assertIn("X_MATCH", ok["env"])

        status, _, created = self.json_request("POST", "/api/profiles", {
            "name": "Solo Cuba", "filters": {"include": "cuba", "lang": "es"},
        })
        self.assertEqual(status, 201, created)
        profile = created["profile"]
        self.assertEqual(profile["name"], "Solo Cuba")

        status, _, duplicated = self.json_request(
            "POST", f"/api/profiles/{profile['id']}/duplicate", {"name": "Copia"}
        )
        self.assertEqual(status, 200, duplicated)
        self.assertEqual(duplicated["profile"]["name"], "Copia")

        preview = self.preview(profile_id=profile["id"])
        self.assertEqual(preview["status"], "done")
        self.assertEqual(preview["params"]["filters"]["include"], ["cuba"])

        status, _, deleted = self.json_request(
            "POST", f"/api/profiles/{profile['id']}", {}
        )
        self.assertEqual(status, 200, deleted)

    def test_inbox_flow_approve_and_apply(self):
        preview = self.preview()
        self.assertEqual(preview["status"], "done")

        status, _, inbox = self.json_request("GET", "/api/inbox")
        self.assertEqual(status, 200, inbox)
        self.assertGreaterEqual(inbox["counts"].get("pending", 0), 2)
        ids = [item["id"] for item in inbox["items"]]
        self.assertEqual(len(ids), 2)

        status, _, decided = self.json_request(
            "POST", "/api/inbox/decide", {"ids": ids[:1], "status": "approved"}
        )
        self.assertEqual(status, 200, decided)
        self.assertEqual(decided["changed"], 1)

        status, _, applied = self.json_request(
            "POST", "/api/inbox/apply", {"delay": 0}
        )
        self.assertEqual(status, 202, applied)
        job = self.wait_job(applied["id"])
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["kind"], "apply")

        status, _, after = self.json_request("GET", "/api/inbox")
        self.assertGreaterEqual(after["counts"].get("verified", 0), 1)

    def test_inbox_rejects_invalid_decision(self):
        status, _, _ = self.json_request("POST", "/api/inbox/decide", {"ids": [], "status": "nope"})
        self.assertEqual(status, 400)
        status, _, _ = self.json_request("POST", "/api/inbox/apply", {})
        self.assertEqual(status, 400)

    def test_inbox_import_validates_shape(self):
        status, _, _ = self.json_request("POST", "/api/inbox/import", {"items": "x"})
        self.assertEqual(status, 400)
        status, _, imported = self.json_request("POST", "/api/inbox/import", {
            "items": [{
                "id": "9",
                "url": "https://x.com/foo/status/9",
                "handle": "foo",
                "author": "Foo",
                "text": "hola",
            }],
        })
        self.assertEqual(status, 200, imported)
        self.assertEqual(imported["imported"], 1)

    def test_schedules_crud_and_preview_only(self):
        run_at = "2099-01-01T10:00:00+00:00"
        status, _, created = self.json_request("POST", "/api/schedules", {
            "name": "Diario",
            "params": self.params(),
            "frequency": "daily",
            "run_at": run_at,
            "enabled": True,
            "notify": True,
        })
        self.assertEqual(status, 201, created)
        item = created["schedule"]
        self.assertEqual(item["frequency"], "daily")

        status, _, listing = self.json_request("GET", "/api/schedules")
        self.assertEqual(status, 200, listing)
        self.assertEqual(len(listing["schedules"]), 1)

        status, _, updated = self.json_request(
            "POST", f"/api/schedules/{item['id']}", {"enabled": False}
        )
        self.assertEqual(status, 200, updated)
        self.assertFalse(updated["schedule"]["enabled"])

        status, _, started = self.json_request(
            "POST", f"/api/schedules/{item['id']}/run", {}
        )
        self.assertEqual(status, 202, started)
        job = self.wait_job(started["id"])
        self.assertEqual(job["kind"], "preview")

        status, _, deleted = self.json_request(
            "POST", f"/api/schedules/{item['id']}/delete", {}
        )
        self.assertEqual(status, 200, deleted)

    def test_schedule_rejects_invalid_frequency(self):
        status, _, body = self.json_request("POST", "/api/schedules", {
            "name": "Mala",
            "params": self.params(),
            "frequency": "hourly",
            "run_at": "2099-01-01T10:00:00+00:00",
        })
        self.assertEqual(status, 400, body)

    def test_stats_diagnostics_and_jobs_list(self):
        self.preview()
        status, _, stats = self.json_request("GET", "/api/stats?days=30")
        self.assertEqual(status, 200, stats)
        self.assertIn("confirmation_rate", stats)
        self.assertIn("by_account", stats)
        self.assertEqual(stats["jobs"]["previews"], 1)

        status, _, diag = self.json_request("GET", "/api/diagnostics")
        self.assertEqual(status, 200, diag)
        self.assertTrue(diag["engine"]["exists"])
        self.assertIn("cdp", diag)
        self.assertIn("history", diag)

        status, _, jobs = self.json_request("GET", "/api/jobs")
        self.assertEqual(status, 200, jobs)
        self.assertGreaterEqual(len(jobs["jobs"]), 1)
        self.assertTrue(all("state" in item for item in jobs["jobs"]))

        status, _, cdp = self.json_request("GET", "/api/cdp")
        self.assertEqual(status, 200, cdp)
        self.assertIn("secure", cdp)

    def test_backup_list_and_restore(self):
        self.apply(self.preview())
        status, _, backup = self.json_request("POST", "/api/backup", {"mode": "history"})
        self.assertEqual(status, 200, backup)
        self.assertTrue(backup["backup"]["path"])

        status, _, listing = self.json_request("GET", "/api/backups")
        self.assertEqual(status, 200, listing)
        self.assertGreaterEqual(len(listing["backups"]), 1)
        backup_path = listing["backups"][0]["path"]

        status, _, restored = self.json_request(
            "POST", "/api/restore", {"path": backup_path, "force": False}
        )
        self.assertEqual(status, 200, restored)
        self.assertTrue(restored["restore"])

        status, _, missing = self.json_request(
            "POST", "/api/restore", {"path": str(self.root / "no-existe.jsonl")}
        )
        self.assertEqual(status, 400)

    def test_export_endpoint_formats(self):
        rows = [{
            "fecha": "2024-01-01",
            "autor": "Autor",
            "usuario": "@foo",
            "texto": "=HYPERLINK(\"http://evil\")",
            "url": "https://x.com/foo/status/1",
            "estado": "reposteado",
        }]
        for fmt, marker in (("csv", "text/csv"), ("json", "application/json")):
            status, headers, body = self.request(
                "POST", "/api/export", {"format": fmt, "rows": rows}
            )
            self.assertEqual(status, 200)
            self.assertIn(marker, headers.get("Content-Type", ""))
            text = body.decode("utf-8")
            self.assertNotIn(",=HYPERLINK", text)
            self.assertIn("'=HYPERLINK", text) if fmt == "csv" else None

        status, _, invalid = self.json_request(
            "POST", "/api/export", {"format": "csv", "rows": "x"}
        )
        self.assertEqual(status, 400, invalid)

    def test_history_diagnostic_endpoint(self):
        self.preview()
        status, _, diag = self.json_request("GET", "/api/history/diagnostic")
        self.assertEqual(status, 200, diag)
        self.assertIn("total_events", diag)
        self.assertIn("corrupt_events", diag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
