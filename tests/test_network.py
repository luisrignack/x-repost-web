#!/usr/bin/env python3
"""Preferencia de red: flags de Chrome, PACs y persistencia (sin navegador)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import xrepost_network as net  # noqa: E402


class NetworkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xrepost-net-test-")
        self.cfg = Path(self.tmp.name) / "network.json"
        self.saved = os.environ.get("XREPOST_NETWORK_CONFIG")
        os.environ["XREPOST_NETWORK_CONFIG"] = str(self.cfg)

    def tearDown(self):
        if self.saved is None:
            os.environ.pop("XREPOST_NETWORK_CONFIG", None)
        else:
            os.environ["XREPOST_NETWORK_CONFIG"] = self.saved
        self.tmp.cleanup()

    def test_default_es_direct_y_flag(self):
        cfg = net.load_config()
        self.assertEqual(cfg["mode"], "direct")
        self.assertEqual(net.chrome_flags(cfg), ["--no-proxy-server"])

    def test_pac_genera_file_uri(self):
        flags = net.chrome_flags({"mode": "pac", "pac_path": str(net.DEFAULT_PAC)})
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0].startswith("--proxy-pac-url=file:///"))
        self.assertTrue(flags[0].endswith("proxy_empresa.pac"))

    def test_auto_usa_el_pac_automatico(self):
        flags = net.chrome_flags({"mode": "auto"})
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0].endswith("proxy_auto.pac"))

    def test_server_incluye_esquema_y_bypass(self):
        flags = net.chrome_flags({
            "mode": "server", "proxy": "proxy.ejemplo.cu:8080",
            "proxy_scheme": "http", "bypass": "localhost,.etecsa.cu",
        })
        self.assertEqual(flags[0], "--proxy-server=http://proxy.ejemplo.cu:8080")
        self.assertEqual(flags[1], "--proxy-bypass-list=localhost,.etecsa.cu")

    def test_server_sin_proxy_se_rechaza(self):
        with self.assertRaises(ValueError):
            net.save_config({"mode": "server", "proxy": ""})

    def test_modo_invalido_se_rechaza(self):
        with self.assertRaises(ValueError):
            net.save_config({"mode": "chino"})
        self.assertEqual(net.load_config()["mode"], "direct")

    def test_roundtrip_persiste(self):
        net.save_config({"mode": "pac", "pac_path": str(net.DEFAULT_PAC)})
        raw = json.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(raw["mode"], "pac")
        self.assertEqual(net.load_config()["mode"], "pac")

    def test_json_roto_cae_a_direct(self):
        self.cfg.write_text("{ roto", encoding="utf-8")
        self.assertEqual(net.load_config()["mode"], "direct")

    def test_pacs_existen_y_tienen_el_contenido_clave(self):
        empresa = net.DEFAULT_PAC.read_text(encoding="utf-8")
        auto = net.AUTO_PAC.read_text(encoding="utf-8")
        self.assertIn("HTTPS internet.etecsa.cu", empresa)
        self.assertIn("dnsResolve", auto)

    def test_cli_flags_y_set(self):
        env = os.environ.copy()
        out = subprocess.run(
            [sys.executable, str(ROOT / "xrepost_network.py"), "set", "server",
             "--proxy", "proxy.ejemplo.cu:8080", "--scheme", "http"],
            env=env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        out = subprocess.run(
            [sys.executable, str(ROOT / "xrepost_network.py"), "flags"],
            env=env, capture_output=True, text=True, timeout=15,
        )
        lineas = out.stdout.strip().splitlines()
        self.assertEqual(lineas[0], "--proxy-server=http://proxy.ejemplo.cu:8080")
        self.assertTrue(lineas[1].startswith("--proxy-bypass-list="))


if __name__ == "__main__":
    unittest.main(verbosity=2)
