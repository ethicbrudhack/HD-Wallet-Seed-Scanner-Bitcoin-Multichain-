import hashlib
import base58
import traceback
import os
import time
import sqlite3
import multiprocessing
import threading
import random
from typing import List, Dict

from mnemonic import Mnemonic
from bip_utils import (
    Bip39SeedGenerator, Bip44, Bip49, Bip84, Bip86,
    Bip44Coins, Bip49Coins, Bip84Coins, Bip86Coins, Bip44Changes
)
import nacl.signing  # Solana

# --------------------------------------------------------
#               USTAWIENIA GLOBALNE
# --------------------------------------------------------
DB_RETRIES = 5            # ile razy ponowić
DB_BACKOFF_BASE = 0.2 
OUTPUT_FILE   = "znalezioneBTCALL.txt"          # gdzie HIT‑y
PROCESSES     = 3                                # liczba procesów‑workerów
MAX_INDEX     = 20                                # ile adresów z każdej ścieżki (0‑MAX_INDEX‑1)
DB_FILE       = "alladdresses1.db"                  # baza z adresami do sprawdzenia
RESULTS_DIR   = "wyniki"                        # tu możesz coś logować

WORD_LENGTHS  = (12, 15, 18, 24)                 # długości seedów
STRENGTH_MAP  = {12: 128, 15: 160, 18: 192, 24: 256}

# --------------------------------------------------------
#                 POMOCNICZE FUNKCJE
# --------------------------------------------------------

def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)

def privkey_to_wif(privkey_hex: str, compressed: bool = True) -> str:
    """Zamienia klucz prywatny hex (Bitcoin‑like) na WIF."""
    key_bytes = bytes.fromhex(privkey_hex)
    prefix = b"\x80" + key_bytes + (b"\x01" if compressed else b"")
    checksum = hashlib.sha256(hashlib.sha256(prefix).digest()).digest()[:4]
    return base58.b58encode(prefix + checksum).decode()

def address_exists_in_db(conn: sqlite3.Connection, address: str, pid: int = None) -> bool:
    """
    Sprawdza adres w bazie danych SQLite (read-only).
    Jeśli baza zablokowana -> pokaże komunikat i zrobi retry.
    """
    attempt = 0
    while True:
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM addresses WHERE address = ?", (address,))
            return cur.fetchone() is not None

        except sqlite3.OperationalError as exc:
            msg = str(exc).lower()
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            who = f"Worker {pid} - " if pid is not None else ""

            # typowy przypadek: "database is locked"
            if "locked" in msg:
                if attempt < DB_RETRIES:
                    backoff = DB_BACKOFF_BASE * (2 ** attempt)
                    print(f"[⚠️] {stamp} {who}Baza zablokowana (próba {attempt+1}/{DB_RETRIES+1}) – czekam {backoff:.2f}s i spróbuję ponownie", flush=True)
                    time.sleep(backoff)
                    attempt += 1
                    continue
                else:
                    print(f"[❌] {stamp} {who}Baza nadal zablokowana po {DB_RETRIES+1} próbach – pomijam zapytanie.", flush=True)
                    return False

            # inne błędy sqlite
            else:
                print(f"[❌] {stamp} {who}Błąd SQLite: {exc}", flush=True)
                traceback.print_exc()
                return False

        except Exception as exc:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            who = f"Worker {pid} - " if pid is not None else ""
            print(f"[❌] {stamp} {who}Inny błąd przy zapytaniu do DB: {exc}", flush=True)
            traceback.print_exc()
            return False

# --------------------------------------------------------
#            GENEROWANIE ADRESÓW HD (WIELE CHAINÓW)
# --------------------------------------------------------

def generate_solana_addresses(seed_phrase: str, max_index: int) -> List[Dict]:
    """Zwraca listę adresów Solany (BIP44). Zapisujemy klucz prywatny w HEX."""
    out: List[Dict] = []
    try:
        seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
        base = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA).Purpose().Coin()
        for i in range(max_index):
            acc = base.Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
            priv_raw = acc.PrivateKey().Raw().ToBytes()
            pub_raw = nacl.signing.SigningKey(priv_raw).verify_key.encode()
            out.append({
                "coin": "SOL",
                "type": "SOLANA-BIP44",
                "index": i,
                "address": base58.b58encode(pub_raw).decode(),
                "hex": priv_raw.hex(),       # klucz prywatny hex
                "seed": seed_phrase,
            })
    except Exception as exc:
        print(f"[WARN] Solana gen error: {exc}", flush=True)
    return out


def generate_hd_addresses(seed_phrase: str, max_index: int = MAX_INDEX) -> List[Dict]:
    """Generuje adresy dla BTC, LTC, DASH, BCH, ETH, DOGE, XRP + Solana."""
    seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
    results: List[Dict] = []

    COIN_MAP = {
        "BTC": [
            ("BIP44", Bip44, Bip44Coins.BITCOIN),
            ("BIP49", Bip49, Bip49Coins.BITCOIN),
            ("BIP84", Bip84, Bip84Coins.BITCOIN),
            ("BIP86", Bip86, Bip86Coins.BITCOIN),
        ],
        "LTC": [
            ("BIP44", Bip44, Bip44Coins.LITECOIN),
            ("BIP49", Bip49, Bip49Coins.LITECOIN),
            ("BIP84", Bip84, Bip84Coins.LITECOIN),
        ],
        "ETH": [("BIP44", Bip44, Bip44Coins.ETHEREUM)],
        "DOGE": [("BIP44", Bip44, Bip44Coins.DOGECOIN)],
        "XRP": [("BIP44", Bip44, Bip44Coins.RIPPLE)],
        "DASH": [("BIP44", Bip44, Bip44Coins.DASH)],
        "BCH": [("BIP44", Bip44, Bip44Coins.BITCOIN_CASH)],
    }

    for coin, derivations in COIN_MAP.items():
        for name, cls, coin_enum in derivations:
            try:
                base = cls.FromSeed(seed_bytes, coin_enum).Purpose().Coin()
                for i in range(max_index):
                    node = base.Account(0).Change(Bip44Changes.CHAIN_EXT).AddressIndex(i)
                    address = node.PublicKey().ToAddress().replace("bitcoincash:", "")
                    priv_hex = node.PrivateKey().Raw().ToHex()
                    results.append({
                        "coin": coin,
                        "type": f"{coin}-{name}",
                        "index": i,
                        "address": address,
                        "wif": privkey_to_wif(priv_hex) if coin in {"BTC", "LTC", "DOGE", "BCH", "DASH"} else priv_hex,
                        "seed": seed_phrase,
                    })
            except Exception:
                continue

    # Solana osobno
    results.extend(generate_solana_addresses(seed_phrase, max_index))
    return results

# --------------------------------------------------------
#              PRODUCER – GENERATOR SEEDÓW
# --------------------------------------------------------

def seed_producer(queue, seed_counter, lock_counter):
    mnemo = Mnemonic("english")

    print("[🎲] Generator losowych seedów 12/15/18/24 słów", flush=True)

    while True:
        length = random.choice(WORD_LENGTHS)
        phrase = mnemo.generate(strength=STRENGTH_MAP[length])  # poprawnie z checksum
        queue.put(phrase)
        with lock_counter:
            seed_counter.value += 1

# --------------------------------------------------------
#                WORKER – SPRAWDZACZ ADRESÓW
# --------------------------------------------------------

def worker_process(queue, lock_io, seed_counter, address_counter, lock_counter, pid):
    print(f"[🔁] Worker {pid} startuje", flush=True)
    # tryb tylko do odczytu (read-only)
    db_uri = f"file:{DB_FILE}?mode=ro"
    try:
        conn = sqlite3.connect(db_uri, uri=True, timeout=5, check_same_thread=False)
    except Exception as exc:
        print(f"[❌] Worker {pid} nie może otworzyć DB '{DB_FILE}': {exc}", flush=True)
        return

    local_addr_count = 0  # lokalny licznik adresów dla danego workera

    while True:
        seed = queue.get()
        if seed is None:
            print(f"[🏁] Worker {pid} kończy", flush=True)
            break

        try:
            addresses = generate_hd_addresses(seed, max_index=MAX_INDEX)

            # --- sprawdzenie w bazie ---
            hit = any(address_exists_in_db(conn, a["address"], pid=pid) for a in addresses)

            if hit:
                print(f"[💥] HIT znaleziony przez worker {pid}!", flush=True)
                with lock_io:
                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(f"✅ HIT!\nSeed: {seed}\n")
                        for e in addresses:
                            if e.get("hex"):
                                f.write(f"{e['type']}[{e['index']}]: {e['address']}\nPriv HEX: {e['hex']}\n")
                            else:
                                f.write(f"{e['type']}[{e['index']}]: {e['address']}\nPriv WIF: {e['wif']}\n")
                        f.write("------------------------------------------------------------\n\n")

            # --- zliczanie adresów ---
            with lock_counter:
                address_counter.value += len(addresses)
                local_addr_count += len(addresses)

                # drukuj tylko co 1000 wygenerowanych adresów
                if address_counter.value % 1000 == 0:
                    print(f"[📊] Worker {pid}: Seeds={seed_counter.value}, Addrs={address_counter.value}", flush=True)

        except Exception as exc:
            print(f"[❌] Worker {pid} error: {exc}", flush=True)

    conn.close()


# --------------------------------------------------------
#                            MAIN
# --------------------------------------------------------

def main():
    ensure_results_dir()
    if not os.path.exists(DB_FILE):
        print(f"[🚫] Brak bazy {DB_FILE}")
        return

    mgr = multiprocessing.Manager()
    seed_cnt = mgr.Value('i', 0)
    addr_cnt = mgr.Value('i', 0)
    lock_cnt = mgr.Lock()
    lock_io  = mgr.Lock()
    q = multiprocessing.Queue(maxsize=PROCESSES * 2)

    prod = multiprocessing.Process(target=seed_producer, args=(q, seed_cnt, lock_cnt))
    prod.start()

    workers = [multiprocessing.Process(target=worker_process,
                                       args=(q, lock_io, seed_cnt, addr_cnt, lock_cnt, i))
               for i in range(PROCESSES)]
    for w in workers:
        w.start()

    def printer():
        while True:
            with lock_cnt:
                print(f"[📊] Seeds: {seed_cnt.value}, Addrs: {addr_cnt.value}", flush=True)
            time.sleep(2)
    threading.Thread(target=printer, daemon=True).start()

    try:
        prod.join()
    except KeyboardInterrupt:
        print("[🛑] SIGINT – kończę…", flush=True)

    for _ in workers:
        q.put(None)
    for w in workers:
        w.join()

    print(f"[🏁] Koniec: Seeds={seed_cnt.value}  Addrs={addr_cnt.value}")


if __name__ == "__main__":
    main()
