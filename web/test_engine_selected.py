#!/usr/bin/env python3
"""Prueba offline de X_ONLY_URLS_FILE con un browser-use simulado.

Verifica que el panel puede aplicar exactamente el listado previsualizado sin
volver a buscar en X y sin abrir Chrome.
"""

from __future__ import annotations

import csv
import json
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "xrepost.sh"

FAKE = textwrap.dedent(
    '''\
    #!/usr/bin/env python3
    import json, os, sys, time

    src = sys.stdin.read()
    log_path = os.environ["FAKE_LOG"]
    NO_BUTTON = os.environ.get("FAKE_NO_BUTTON") == "1"
    QUOTE_TOAST = os.environ.get("FAKE_QUOTE_TOAST", "1") == "1"
    NO_QUOTE_MENU = os.environ.get("FAKE_NO_QUOTE_MENU") == "1"
    NO_COMPOSER = os.environ.get("FAKE_NO_COMPOSER") == "1"
    DISABLED = os.environ.get("FAKE_DISABLED") == "1"
    RETWEETED = os.environ.get("FAKE_RETWEETED") == "1"
    UNDO_FAIL = os.environ.get("FAKE_UNDO_FAIL") == "1"
    RESULTS = json.loads(os.environ.get("FAKE_RESULTS", "[]"))
    collected = {"done": False}

    def initial():
        return {"unretweet": RETWEETED, "menu": False,
                "composer": False, "toast": False}

    state = initial()

    def log(line):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\\n")

    def goto_url(url):
        state.update(initial())
        log("GOTO " + url)

    def wait_for_load():
        pass

    def type_text(text):
        log("TYPE " + text)

    def js(expr):
        if "unretweetConfirm" in expr:
            if ".click()" in expr:
                state["unretweet"] = UNDO_FAIL
            return True
        if "retweetConfirm" in expr:
            if ".click()" in expr:
                state["unretweet"] = True
            return True
        if 'data-testid="toast"' in expr:
            return state["toast"]
        if 'role="menuitem"' in expr:
            if ".click()" in expr:
                state["menu"] = False
                state["composer"] = not NO_COMPOSER
                return None
            return state["menu"] and not NO_QUOTE_MENU
        if "tweetButton" in expr and (".click()" in expr or "aria-disabled" in expr):
            if "aria-disabled" in expr:
                return DISABLED
            if ".click()" in expr:
                if DISABLED:
                    return False
                state["composer"] = False
                state["toast"] = QUOTE_TOAST
                return True
            return False
        if "window.scrollBy" in expr:
            return None
        if "tweetTextarea_0" in expr:
            return state["composer"]
        if 'data-testid="unretweet"' in expr:
            return 1 if state["unretweet"] else 0
        if 'data-testid="retweet"' in expr:
            if ".click()" in expr:
                state["menu"] = True
                return None
            return 0 if (state["unretweet"] or NO_BUTTON) else 1
        if 'article[data-testid="tweet"]' in expr:
            if ".map(function(a)" in expr:
                if collected["done"]:
                    return []
                collected["done"] = True
                return RESULTS
            return len(RESULTS)
        raise AssertionError("js inesperado: " + expr)

    time.sleep = lambda *args, **kwargs: None
    ns = {
        "__name__": "__main__",
        "js": js,
        "goto_url": goto_url,
        "wait_for_load": wait_for_load,
        "type_text": type_text,
    }
    try:
        exec(compile(src, "xrepost.py", "exec"), ns)
    except SystemExit as exc:
        raise SystemExit(exc.code)
    '''
)

POSTS = [
    {
        "fecha": "2024-01-01 10:00",
        "autor": "Autor Uno",
        "usuario": "@foo",
        "texto": "primer post seleccionado",
        "url": "https://x.com/foo/status/11",
        "estado": "solo listado",
    },
    {
        "fecha": "2024-01-02 11:30",
        "autor": "Autor Dos",
        "usuario": "@bar",
        "texto": "segundo post seleccionado",
        "url": "https://x.com/bar/status/22",
        "estado": "solo listado",
    },
]


class EngineSelectedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xrepost-engine-test-")
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        fake = self.bin / "browser-use"
        fake.write_text(FAKE, encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
        self.selected = self.root / "selected.json"
        self.selected.write_text(json.dumps(POSTS, ensure_ascii=False), encoding="utf-8")
        self.history = self.root / "history.jsonl"
        self.csv = self.root / "posts.csv"
        self.md = self.root / "posts.md"
        self.log = self.root / "browser.log"

    def tearDown(self):
        self.tmp.cleanup()

    def run_engine(self, limit=10, extra_env=None, args=None):
        env = os.environ.copy()
        env.update(
            {
                "PATH": f"{self.bin}:{env.get('PATH', '')}",
                "FAKE_LOG": str(self.log),
                "X_ONLY_URLS_FILE": str(self.selected),
                "X_APPLY": "1",
                "X_USERS": "foo",
                "X_FROM": "2024-01-01",
                "X_TO": "2024-01-31",
                "X_HISTORY": str(self.history),
                "X_CSV": str(self.csv),
                "X_MD": str(self.md),
                "X_LIMIT": str(limit),
                "X_DELAY": "0",
                "NO_COLOR": "1",
            }
        )
        env.update(extra_env or {})
        return subprocess.run(
            [str(SH), "--csv", str(self.csv), "--md", str(self.md)] + list(args or []),
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def run_cli(self, args, extra_env=None):
        """Ejecuta la CLI con el navegador falso (búsqueda/undo, sin listado previo)."""
        env = os.environ.copy()
        for clave in ("X_ONLY_URLS_FILE", "X_UNDO_TARGET", "X_UNDO_N", "X_QUOTE"):
            env.pop(clave, None)
        env.update(
            {
                "PATH": f"{self.bin}:{env.get('PATH', '')}",
                "FAKE_LOG": str(self.log),
                "X_HISTORY": str(self.history),
                "X_CSV": str(self.csv),
                "X_MD": str(self.md),
                "X_DELAY": "0",
                "NO_COLOR": "1",
            }
        )
        env.update(extra_env or {})
        return subprocess.run(
            [str(SH), "--csv", str(self.csv), "--md", str(self.md)] + list(args),
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def seed_reposts(self):
        self.history.write_text(
            "".join(
                json.dumps(
                    {
                        "ts": "2024-01-02T09:00:00Z",
                        "run": "tanda-1",
                        "action": "repost",
                        "result": "reposted",
                        "id": str(num),
                        "url": post["url"],
                        "handle": "foo",
                    },
                    ensure_ascii=False,
                )
                + "\n"
                for num, post in enumerate(POSTS, 1)
            ),
            encoding="utf-8",
        )

    def history_results(self, action=None):
        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        if action:
            events = [e for e in events if e["action"] == action]
        return [e["result"] for e in events]

    def test_applies_exact_selected_urls_without_searching(self):
        result = self.run_engine()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("listado de la previsualización", result.stdout)

        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [post["url"] for post in POSTS])
        self.assertFalse(any("search?q=" in url for url in visited))

        rows = list(csv.DictReader(self.csv.read_text("utf-8").splitlines()))
        self.assertEqual([row["url"] for row in rows], [post["url"] for post in POSTS])
        self.assertTrue(all(row["estado"] == "reposteado" for row in rows))
        self.assertIn("segundo post seleccionado", self.md.read_text("utf-8"))

        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(events), 2)
        self.assertEqual([e["id"] for e in events], ["11", "22"])
        self.assertTrue(all(e["action"] == "repost" and e["result"] == "reposted" for e in events))

    def test_skips_posts_already_done_in_history(self):
        # Reaplicar un listado no debe repetir nada: las citas no se pueden
        # verificar ni deshacer desde el DOM como los reposts.
        self.history.write_text(
            json.dumps(
                {
                    "ts": "2024-01-02T09:00:00Z",
                    "run": "run-anterior",
                    "action": "repost",
                    "result": "quoted",
                    "id": "11",
                    "url": POSTS[0]["url"],
                    "handle": "foo",
                    "author": "Autor Uno",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        result = self.run_engine()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sobre 1 publicaciones revisadas", result.stdout)
        self.assertIn("ya reposteados o citados", result.stdout)

        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [POSTS[1]["url"]])

        rows = list(csv.DictReader(self.csv.read_text("utf-8").splitlines()))
        self.assertEqual([row["url"] for row in rows], [POSTS[1]["url"]])

        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([e["id"] for e in events if e.get("run") != "run-anterior"], ["22"])

    def test_ignores_non_x_urls(self):
        data = [POSTS[0], {"url": "https://evil.example/status/1", "texto": "no"}]
        self.selected.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_engine()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("URL no válida", result.stdout)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [POSTS[0]["url"]])
        rows = list(csv.DictReader(self.csv.read_text("utf-8").splitlines()))
        self.assertEqual([row["url"] for row in rows], [POSTS[0]["url"]])

    def test_limit_caps_selected_list(self):
        result = self.run_engine(limit=1)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [POSTS[0]["url"]])
        self.assertIn("límite de 1 alcanzado", result.stdout)


    def test_invalid_limit_exits_with_clear_message(self):
        result = self.run_engine(extra_env={"X_LIMIT": "abc"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("X_LIMIT no es un número válido", result.stdout)

    def test_circuit_breaker_stops_after_three_failures(self):
        posts = [
            dict(POSTS[0], url=f"https://x.com/foo/status/{i}") for i in range(1, 6)
        ]
        self.selected.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(extra_env={"FAKE_NO_BUTTON": "1"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(len(visited), 3)
        self.assertIn("3 fallos seguidos", result.stdout)

    def test_quote_requires_confirmation_toast(self):
        self.selected.write_text(json.dumps(POSTS[:1], ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(extra_env={"X_QUOTE": "#ETECSA"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([e["result"] for e in events], ["quoted"])
        self.assertEqual(events[0]["quote"], "#ETECSA")
        self.assertIn("TYPE #ETECSA", self.log.read_text("utf-8"))

    def test_quote_without_toast_is_not_marked_done(self):
        self.selected.write_text(json.dumps(POSTS[:1], ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(
            extra_env={"X_QUOTE": "#ETECSA", "FAKE_QUOTE_TOAST": "0"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual([e["result"] for e in events], ["quote_unverified"])
        self.assertIn("cita sin confirmar", result.stdout)

        # Un segundo intento NO vuelve a visitar el post: quedó sin confirmar y
        # reintentar a ciegas podría duplicar la cita. Solo --force lo reintenta.
        self.log.write_text("", encoding="utf-8")
        result = self.run_engine(extra_env={"X_QUOTE": "#ETECSA"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [])
        self.assertIn("sin confirmar", result.stdout)

        # Con --force el usuario asume el riesgo y se reintenta.
        result = self.run_engine(
            args=["--force"], extra_env={"X_QUOTE": "#ETECSA"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [POSTS[0]["url"]])

    def test_posted_at_normalized_to_iso(self):
        posts = [dict(POSTS[0], fecha="01/01/2024 10:00")]
        self.selected.write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
        result = self.run_engine()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = [
            json.loads(line)
            for line in self.history.read_text("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(events[0]["posted_at"], "2024-01-01T10:00")

    def test_collect_filtra_respuestas_retweets_y_palabras(self):
        resultados = [
            {"time": "2024-01-10T10:00:00Z", "url": "https://x.com/foo/status/1",
             "handle": "foo", "user": "Foo", "text": "kubernetes es util", "ctx": "", "reply": False},
            {"time": "2024-01-11T10:00:00Z", "url": "https://x.com/foo/status/2",
             "handle": "foo", "user": "Foo", "text": "respuesta", "ctx": "", "reply": True},
            {"time": "2024-01-12T10:00:00Z", "url": "https://x.com/otro/status/3",
             "handle": "otro", "user": "Otro", "text": "kubernetes", "ctx": "", "reply": False},
            {"time": "2024-01-13T10:00:00Z", "url": "https://x.com/foo/status/4",
             "handle": "foo", "user": "Foo", "text": "oferta de empleo", "ctx": "", "reply": False},
            {"time": "2024-02-01T10:00:00Z", "url": "https://x.com/foo/status/5",
             "handle": "foo", "user": "Foo", "text": "fuera de rango", "ctx": "", "reply": False},
            {"time": "2024-01-14T10:00:00Z", "url": "https://x.com/foo/status/1",
             "handle": "foo", "user": "Foo", "text": "duplicado", "ctx": "", "reply": False},
        ]
        result = self.run_cli(
            ["foo", "2024-01-01", "2024-01-31"],
            {
                "FAKE_RESULTS": json.dumps(resultados, ensure_ascii=False),
                "X_EXCLUDE": "empleo",
                "X_SKIP_REPLIES": "1",
                "X_SKIP_RETWEETS": "1",
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = list(csv.DictReader(self.csv.read_text("utf-8").splitlines()))
        self.assertEqual([row["url"] for row in rows], ["https://x.com/foo/status/1"])

    def test_undo_last_y_reintento_tras_undo_failed(self):
        self.seed_reposts()
        result = self.run_cli(
            ["--undo-last"], {"FAKE_RETWEETED": "1", "FAKE_UNDO_FAIL": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.history_results("undo"), ["undo_failed", "undo_failed"])
        self.assertIn("Total deshecho: 0", result.stdout)

        # undo_failed no quita el repost del estado: la segunda pasada reintenta.
        self.log.write_text("", encoding="utf-8")
        result = self.run_cli(["--undo-last"], {"FAKE_RETWEETED": "1"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(
            self.history_results("undo"),
            ["undo_failed", "undo_failed", "undone", "undone"],
        )
        self.assertIn("Total deshecho: 2", result.stdout)
        self.assertEqual(
            len([line for line in self.log.read_text("utf-8").splitlines()
                 if line.startswith("GOTO ")]),
            2,
        )

    def test_undo_url_concreta(self):
        self.seed_reposts()
        result = self.run_cli(
            ["--undo", POSTS[1]["url"]], {"FAKE_RETWEETED": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        visited = [
            line[5:]
            for line in self.log.read_text("utf-8").splitlines()
            if line.startswith("GOTO ")
        ]
        self.assertEqual(visited, [POSTS[1]["url"]])
        self.assertEqual(self.history_results("undo"), ["undone"])

    def test_quote_sin_opcion_de_cita(self):
        self.selected.write_text(json.dumps(POSTS[:1], ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(
            extra_env={"X_QUOTE": "#ETECSA", "FAKE_NO_QUOTE_MENU": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.history_results("repost"), ["no_quote_option"])

    def test_quote_sin_composer(self):
        self.selected.write_text(json.dumps(POSTS[:1], ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(
            extra_env={"X_QUOTE": "#ETECSA", "FAKE_NO_COMPOSER": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.history_results("repost"), ["no_composer"])

    def test_quote_boton_deshabilitado(self):
        self.selected.write_text(json.dumps(POSTS[:1], ensure_ascii=False), encoding="utf-8")
        result = self.run_engine(
            extra_env={"X_QUOTE": "#ETECSA", "FAKE_DISABLED": "1"}
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.history_results("repost"), ["quote_failed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
