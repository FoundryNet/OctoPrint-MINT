import json, hashlib, os, struct, time
from typing import Optional
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import ID as SYSTEM_PROGRAM_ID
from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solders.transaction import Transaction
from solders.instruction import Instruction, AccountMeta

PROGRAM_ID = Pubkey.from_string("4ZvTZ3skfeMF3ZGyABoazPa9tiudw2QSwuVKn45t2AKL")
STATE_ACCOUNT = Pubkey.from_string("2Lm7hrtqK9W5tykVu4U37nUNJiiFh6WQ1rD8ZJWXomr2")
DEFAULT_RPC = "https://api.mainnet-beta.solana.com"
BASE_RATE = 0.005
DISCRIMINATORS = {
    "register_machine": bytes([168, 160, 68, 209, 28, 151, 41, 17]),
    "record_job": bytes([54, 124, 168, 158, 236, 237, 107, 206]),
}

class FoundryClient:
    def __init__(self, rpc_url=DEFAULT_RPC, keypair_path=None):
        self.client = Client(rpc_url)
        self.rpc_url = rpc_url
        self.keypair = None
        self.machine_pubkey = None
        if keypair_path and os.path.exists(keypair_path):
            self.load_keypair(keypair_path)

    def load_keypair(self, path):
        with open(path) as f: secret = json.load(f)
        self.keypair = Keypair.from_bytes(bytes(secret))
        self.machine_pubkey = self.keypair.pubkey()
        return self.machine_pubkey

    def generate_keypair(self, save_path):
        self.keypair = Keypair()
        self.machine_pubkey = self.keypair.pubkey()
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        with open(save_path, "w") as f: json.dump(list(bytes(self.keypair)), f)
        return self.machine_pubkey

    def derive_machine_state_pda(self):
        pda, _ = Pubkey.find_program_address([b"machine", bytes(self.machine_pubkey)], PROGRAM_ID)
        return pda

    def register_machine(self, fee_payer):
        if not self.keypair: raise ValueError("No keypair loaded")
        pda = self.derive_machine_state_pda()
        accounts = [
            AccountMeta(pubkey=pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=self.machine_pubkey, is_signer=True, is_writable=False),
            AccountMeta(pubkey=fee_payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=STATE_ACCOUNT, is_signer=False, is_writable=True),
            AccountMeta(pubkey=SYSTEM_PROGRAM_ID, is_signer=False, is_writable=False),
        ]
        ix = Instruction(PROGRAM_ID, DISCRIMINATORS["register_machine"], accounts)
        try:
            bh = self.client.get_latest_blockhash(Confirmed).value.blockhash
            tx = Transaction.new_signed_with_payer([ix], fee_payer.pubkey(), [fee_payer, self.keypair], bh)
            return str(self.client.send_transaction(tx).value)
        except Exception as e:
            print(f"register_machine failed: {e}"); return None

    def record_job(self, job_hash, duration_seconds, complexity, fee_payer):
        if not self.keypair: raise ValueError("No keypair loaded")
        pda = self.derive_machine_state_pda()
        data = bytearray(DISCRIMINATORS["record_job"])
        data.extend(hashlib.sha256(job_hash.encode()).digest())
        data.extend(struct.pack("<Q", duration_seconds))
        data.extend(struct.pack("<Q", complexity))
        accounts = [
            AccountMeta(pubkey=pda, is_signer=False, is_writable=True),
            AccountMeta(pubkey=self.machine_pubkey, is_signer=True, is_writable=False),
            AccountMeta(pubkey=fee_payer.pubkey(), is_signer=True, is_writable=True),
            AccountMeta(pubkey=STATE_ACCOUNT, is_signer=False, is_writable=True),
        ]
        ix = Instruction(PROGRAM_ID, bytes(data), accounts)
        try:
            bh = self.client.get_latest_blockhash(Confirmed).value.blockhash
            signers = [fee_payer, self.keypair] if fee_payer.pubkey() != self.machine_pubkey else [self.keypair]
            tx = Transaction.new_signed_with_payer([ix], fee_payer.pubkey(), signers, bh)
            return str(self.client.send_transaction(tx).value)
        except Exception as e:
            print(f"record_job failed: {e}"); return None

    def estimate_reward(self, duration_seconds, complexity=1.0, trust=100, job_count=0):
        warmup = 0.5 + (0.5 * min(job_count, 30) / 30)
        base = duration_seconds * BASE_RATE * complexity * (trust / 100) * warmup
        return {"base_reward": round(base, 6), "worker_share": round(base * 0.96, 6),
                "protocol_fee": round(base * 0.02, 6), "personal_fee": round(base * 0.02, 6),
                "warmup": round(warmup, 4), "duration_seconds": duration_seconds,
                "complexity": complexity, "trust": trust}

    @staticmethod
    def generate_job_hash(filename, extra=""):
        return hashlib.sha256(f"{filename}:{extra}:{time.time()}:{os.getpid()}".encode()).hexdigest()
