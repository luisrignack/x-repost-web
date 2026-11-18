#!/usr/bin/env python3
"""Arranque de un comando: sintaxis, modos sin efecto y contenido clave."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "iniciar.sh"
CHROME = ROOT / "xrepost-chrome.sh"


class StartScriptTest(unittest.TestCase):
    def setUp(self):
        # iniciar.sh --check exige browser-use en el PATH. En un runner de CI
        # no está instalado (y no debe estarlo: la suite no abre Chrome), así
        # que se inyecta un doble inocuo para probar la lógica del script.
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        bindir = Path(self.tmp.name)
        fake = bindir / "browser-use"
        fake.write_text("#!/bin/sh\necho 'browser-use 0.0-test'\n", encoding="utf-8")
        fake.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = f"{bindir}{os.pathsep}{self.env.get('PATH', '')}"

    def run_script(self, *args):
        return subprocess.run(
            ["bash", str(START), *args], cwd=str(ROOT), env=self.env,
            capture_output=True, text=True, timeout=30,
        )

    def test_sintaxis_de_los_scripts(self):
        for script in (START, CHROME, ROOT / "xrepost-portable" / "start.sh"):
            proc = subprocess.run(
                ["bash", "-n", str(script)], capture_output=True, text=True, timeout=10
            )
            self.assertEqual(proc.returncode, 0, f"{script.name}: {proc.stderr}")

    def test_check_y_status_no_tienen_efectos_secundarios(self):
        for flag in ("--check", "--status"):
            proc = self.run_script(flag)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Panel:", proc.stdout)
            self.assertIn("Chrome CDP:", proc.stdout)

    def test_help_lista_los_modos(self):
        proc = self.run_script("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for token in ("--status", "--stop", "--check", "--no-open"):
            self.assertIn(token, proc.stdout)

    def test_lanzador_usa_binario_real_y_limpia_locks(self):
        src = CHROME.read_text(encoding="utf-8")
        self.assertIn("/opt/google/chrome/chrome", src)
        self.assertIn("SingletonLock", src)
        self.assertIn("python3 xrepost_network.py flags", src)
        # El wrapper google-chrome NO debe usarse para arrancar: delega en la
        # instancia abierta e ignora --user-data-dir. CHROME ya es el binario real.
        self.assertNotIn("nohup google-chrome", src)
        self.assertIn('CHROME="$(chrome_binary || true)"', src)

    def test_iniciar_reutiliza_y_tiene_stop(self):
        src = START.read_text(encoding="utf-8")
        self.assertIn('bash "$DIR/xrepost-chrome.sh"', src)
        self.assertIn("--stop", src)
        self.assertIn("ya estaba arriba", src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
