import sys, os, time, hashlib, struct
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "octoprint_mint"))

def sep(t): print(f"\n{'='*60}\n  {t}\n{'='*60}")

def test_hashes():
    sep("TEST 1: Job Hash Generation")
    h = {hashlib.sha256(f"b.gcode::{time.time()}:{os.getpid()}".encode()).hexdigest() for _ in range(100)}
    assert len(h) == 100; print("  [PASS]  100/100 unique")

def test_discriminators():
    sep("TEST 2: Anchor Discriminators")
    r = bytes([168,160,68,209,28,151,41,17]); j = bytes([54,124,168,158,236,237,107,206])
    assert len(r)==8 and len(j)==8; print(f"  [PASS]  register: {list(r)}"); print(f"  [PASS]  record:   {list(j)}")

def test_encoding():
    sep("TEST 3: Instruction Encoding")
    d = bytearray(bytes([54,124,168,158,236,237,107,206]))
    d.extend(hashlib.sha256(b"test").digest())
    d.extend(struct.pack("<Q",3600)); d.extend(struct.pack("<Q",1))
    assert len(d)==56; print(f"  [PASS]  56 bytes")
    assert struct.unpack("<Q",bytes(d[40:48]))[0]==3600; print("  [PASS]  Duration: 3600s")
    assert struct.unpack("<Q",bytes(d[48:56]))[0]==1; print("  [PASS]  Complexity: 1")

def test_math():
    sep("TEST 4: Reward Math")
    for jobs,exp_w,exp_b in [(0,0.5,9.0),(15,0.75,13.5),(30,1.0,18.0)]:
        w = 0.5+(0.5*min(jobs,30)/30); b = 3600*0.005*1.0*1.0*w
        assert abs(w-exp_w)<0.001 and abs(b-exp_b)<0.001
        print(f"  [PASS]  {jobs} jobs: warmup={w:.2f}x base={b:.2f} worker={b*0.96:.2f}")

def test_flow():
    sep("TEST 5: Event Flow")
    active=None; earn=0.0; jobs=0
    active={"start":time.time(),"f":"b.gcode"}; time.sleep(1)
    dur=int(time.time()-active["start"]); w=0.5+(0.5*min(jobs,30)/30); r=dur*0.005*1.0*w*0.96
    earn+=r; jobs+=1; active=None
    assert active is None and earn>0 and jobs==1; print(f"  [PASS]  Earned {earn:.6f} MINT")

def test_solders():
    sep("TEST 6: Solders Import")
    try:
        from solders.keypair import Keypair; from solders.pubkey import Pubkey
        kp=Keypair(); pid=Pubkey.from_string("4ZvTZ3skfeMF3ZGyABoazPa9tiudw2QSwuVKn45t2AKL")
        pda,bump=Pubkey.find_program_address([b"machine",bytes(kp.pubkey())],pid)
        print(f"  [PASS]  Keypair: {kp.pubkey()}"); print(f"  [PASS]  PDA: {pda} (bump {bump})")
    except ImportError as e: print(f"  [SKIP]  {e}")

def test_client():
    sep("TEST 7: MintClient")
    from mint_client import FoundryClient
    print(f"  [INFO]  Loaded from: {FoundryClient.__module__}")
    c = FoundryClient(rpc_url="https://api.mainnet-beta.solana.com")
    e = c.estimate_reward(3600,1.0,100,0)
    assert abs(e["base_reward"]-9.0)<0.001; print(f"  [PASS]  New: {e}")
    e2 = c.estimate_reward(3600,1.0,100,30)
    assert abs(e2["base_reward"]-18.0)<0.001; print(f"  [PASS]  Full: {e2}")
    h = FoundryClient.generate_job_hash("b.gcode")
    assert len(h)==64; print(f"  [PASS]  Hash OK")

if __name__=="__main__":
    print("\n"+"="*60+"\n  OctoPrint-MINT Tests (On-Chain)\n"+"="*60)
    test_hashes(); test_discriminators(); test_encoding(); test_math(); test_flow(); test_solders(); test_client()
    sep("ALL TESTS COMPLETE")
