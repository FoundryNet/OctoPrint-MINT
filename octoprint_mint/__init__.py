import octoprint.plugin
from octoprint.events import Events
import os, json, time, threading
from .mint_client import FoundryClient, BASE_RATE

class MintPlugin(
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SettingsPlugin,
    octoprint.plugin.TemplatePlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.EventHandlerPlugin,
    octoprint.plugin.SimpleApiPlugin,
):
    def on_after_startup(self):
        self._logger.info("MINT Plugin started | Direct on-chain")
        self._active_print = None
        self._session_earnings = 0.0
        self._total_jobs = 0
        self._lifetime_earnings = self._settings.get_float(["lifetime_earnings"]) or 0.0
        self._registered = False
        self._foundry = None
        self._fee_payer = None
        self._init_client()

    def _init_client(self):
        rpc = self._settings.get(["rpc_url"]) or "https://api.mainnet-beta.solana.com"
        self._foundry = FoundryClient(rpc_url=rpc)
        mkp = self._settings.get(["machine_keypair_path"])
        fkp = self._settings.get(["fee_payer_keypair_path"])
        if mkp and os.path.exists(mkp):
            pub = self._foundry.load_keypair(mkp)
            self._logger.info(f"MINT: Machine keypair: {pub}")
        else:
            d = os.path.expanduser("~/.foundry"); os.makedirs(d, exist_ok=True)
            p = os.path.join(d, "octoprint_machine_keypair.json")
            if os.path.exists(p):
                pub = self._foundry.load_keypair(p)
            else:
                pub = self._foundry.generate_keypair(p)
                self._logger.info(f"MINT: Generated new machine keypair: {pub}")
            self._settings.set(["machine_keypair_path"], p); self._settings.save()
        if fkp and os.path.exists(fkp):
            from solders.keypair import Keypair
            with open(fkp) as f: secret = json.load(f)
            self._fee_payer = Keypair.from_bytes(bytes(secret))
            self._logger.info(f"MINT: Fee payer: {self._fee_payer.pubkey()}")
        else:
            self._logger.warning("MINT: No fee payer keypair. Set in Settings > MINT.")

    def get_settings_defaults(self):
        return dict(rpc_url="https://api.mainnet-beta.solana.com", machine_keypair_path="",
                    fee_payer_keypair_path="", auto_settle=True, complexity_default=1,
                    lifetime_earnings=0.0, show_navbar=True)

    def get_settings_restricted_paths(self):
        return dict(admin=[["fee_payer_keypair_path"]])

    def get_template_configs(self):
        return [dict(type="settings", custom_bindings=True),
                dict(type="tab", custom_bindings=True),
                dict(type="navbar", custom_bindings=True)]

    def get_assets(self):
        return dict(js=["js/mint.js"], css=["css/mint.css"])

    def on_event(self, event, payload):
        if event == Events.PRINT_STARTED:
            fn = payload.get("name", "unknown")
            jh = FoundryClient.generate_job_hash(fn, payload.get("path", ""))
            self._active_print = {"job_hash": jh, "filename": fn, "start_time": time.time()}
            self._logger.info(f"MINT: Print started | {fn}")
            self._send("print_started", {"filename": fn, "job_hash": jh[:16]})
        elif event == Events.PRINT_DONE:
            if not self._active_print: return
            dur = int(time.time() - self._active_print["start_time"])
            jh, fn = self._active_print["job_hash"], self._active_print["filename"]
            self._logger.info(f"MINT: Print done | {fn} | {dur}s")
            if self._settings.get(["auto_settle"]):
                threading.Thread(target=self._submit, args=(jh, dur, fn), daemon=True).start()
            self._active_print = None
        elif event in (Events.PRINT_FAILED, Events.PRINT_CANCELLED):
            if self._active_print:
                s = "failed" if event == Events.PRINT_FAILED else "cancelled"
                self._send(f"print_{s}", {"filename": self._active_print["filename"],
                                           "reason": f"Print {s}, no MINT earned"})
                self._active_print = None

    def _submit(self, job_hash, duration, filename):
        if not self._foundry or not self._foundry.keypair:
            self._send("error", {"message": "No machine keypair"}); return
        if not self._fee_payer:
            self._send("error", {"message": "No fee payer keypair"}); return
        comp = self._settings.get_int(["complexity_default"]) or 1
        if not self._registered and self._total_jobs == 0:
            self._foundry.register_machine(self._fee_payer)
            self._registered = True
        sig = self._foundry.record_job(job_hash, duration, comp, self._fee_payer)
        if sig:
            est = self._foundry.estimate_reward(duration, float(comp), 100, self._total_jobs)
            rw = est["worker_share"]
            self._session_earnings += rw; self._total_jobs += 1; self._lifetime_earnings += rw
            self._settings.set_float(["lifetime_earnings"], self._lifetime_earnings); self._settings.save()
            self._logger.info(f"MINT: On-chain! tx:{sig[:20]}... est:{rw:.4f}")
            self._send("job_settled", {"filename": filename, "duration_seconds": duration,
                "reward": rw, "session_earnings": self._session_earnings,
                "lifetime_earnings": self._lifetime_earnings, "total_jobs": self._total_jobs,
                "tx_url": f"https://solscan.io/tx/{sig}", "signature": sig})
        else:
            self._send("error", {"message": "Failed to submit on-chain"})

    def get_api_commands(self):
        return dict(status=[], simulate=["duration_seconds"], register=[])

    def on_api_command(self, command, data):
        import flask
        if command == "status":
            mid = str(self._foundry.machine_pubkey) if self._foundry and self._foundry.machine_pubkey else None
            return flask.jsonify({"machine_id": mid, "session_earnings": self._session_earnings,
                "lifetime_earnings": self._lifetime_earnings, "total_jobs": self._total_jobs,
                "registered": self._registered, "fee_payer_loaded": self._fee_payer is not None})
        elif command == "simulate":
            if self._foundry:
                return flask.jsonify(self._foundry.estimate_reward(data.get("duration_seconds", 3600),
                    job_count=self._total_jobs))
            return flask.jsonify({"error": "Not initialized"}), 500
        elif command == "register":
            if not self._foundry or not self._fee_payer:
                return flask.jsonify({"error": "Not configured"}), 500
            sig = self._foundry.register_machine(self._fee_payer)
            if sig: self._registered = True; return flask.jsonify({"status": "registered", "signature": sig})
            return flask.jsonify({"error": "Failed"}), 500

    def _send(self, t, d):
        self._plugin_manager.send_plugin_message(self._identifier, dict(type=t, data=d))

__plugin_name__ = "MINT Protocol"
__plugin_version__ = "1.0.0"
__plugin_description__ = "Earn MINT for 3D prints. Direct on-chain via Solana."
__plugin_pythoncompat__ = ">=3.7,<4"
__plugin_implementation__ = MintPlugin()
