🔐 HD Wallet Seed Scanner (Bitcoin & Multichain)

This Python script generates random BIP-39 mnemonic seed phrases, derives their HD wallet addresses for multiple blockchains (Bitcoin, Ethereum, Solana, Litecoin, Dogecoin, etc.), and checks whether any of those addresses appear in a local SQLite address database.

It is built purely for research and educational purposes — to understand how HD wallet derivation and BIP-standards work in practice.

⚙️ Overview

The script continuously:

Generates valid random mnemonic phrases (12/15/18/24 words) using the BIP-39 checksum system.

Derives deterministic wallet addresses for multiple coins using BIP-44, BIP-49, BIP-84, and BIP-86 standards.

Checks each generated address against an existing SQLite database (alladdresses1.db) of known addresses.

Logs matches ("hits") to an output file (znalezioneBTCALL.txt).

It runs in parallel (multi-process) to maximize throughput and includes smart retry logic for database locks.

🔧 Supported Blockchains
Coin	Derivation Standards Supported
Bitcoin (BTC)	BIP-44 / BIP-49 / BIP-84 / BIP-86
Litecoin (LTC)	BIP-44 / BIP-49 / BIP-84
Bitcoin Cash (BCH)	BIP-44
Dogecoin (DOGE)	BIP-44
Dash (DASH)	BIP-44
Ethereum (ETH)	BIP-44
Ripple (XRP)	BIP-44
Solana (SOL)	BIP-44 (via NaCl signing)
🧩 File Structure
File	Description
main.py	Main script file
alladdresses1.db	SQLite database containing addresses to check
znalezioneBTCALL.txt	Output log file for hits
wyniki/	Directory for logs or optional output files
📦 Requirements

Install all dependencies with:

pip install base58 mnemonic bip-utils pynacl


or individually:

pip install base58
pip install mnemonic
pip install bip-utils
pip install pynacl

🧰 Features

✅ Multi-process architecture (configurable number of workers)
✅ Multi-chain address generation (BTC, ETH, SOL, etc.)
✅ Automatic retry if database is locked
✅ Safe read-only SQLite operations
✅ Real-time progress display (Seeds and Addrs counters)
✅ Modular and extendable — you can add more coins easily

⚙️ Configuration (Global Settings)

Inside the script you can adjust:

Variable	Description	Default
PROCESSES	Number of worker processes	3
MAX_INDEX	Number of derived addresses per derivation path	20
DB_FILE	SQLite database file	alladdresses1.db
OUTPUT_FILE	File for saving hits	znalezioneBTCALL.txt
WORD_LENGTHS	Mnemonic lengths to generate	(12, 15, 18, 24)
▶️ How to Run

Make sure you have the database file (e.g., alladdresses1.db) in the same directory.
The database must contain a table called addresses with a column named address.

Run the script:

python3 main.py


The script will:

Start generating seeds and addresses.

Check them against the database.

Print live progress and save any “hits” to znalezioneBTCALL.txt.

To stop it safely, use Ctrl + C.

📄 Example Output (Partial)
[🎲] Generator losowych seedów 12/15/18/24 słów
[🔁] Worker 1 startuje
[📊] Worker 2: Seeds=100, Addrs=2000
[💥] HIT znaleziony przez worker 0!
✅ HIT!
Seed: bone tribe entry poem century chair paper ...
BTC-BIP44[0]: 1BoatSLRHtKNngkdXEeobR76b53LETtpyT
Priv WIF: Kz3s7Y2...
------------------------------------------------------------

🧠 How It Works (Technical Summary)

Mnemonic generation: Uses mnemonic.Mnemonic with valid checksum.

Seed derivation: Uses Bip39SeedGenerator → Bip44, Bip49, Bip84, Bip86.

Address creation: Converts private keys to WIF (for Bitcoin-like coins) and derives public addresses.

Database checking: Queries SQLite with retries on lock errors.

Parallel execution: Spawns multiple worker processes via multiprocessing.

Thread-safe logging: Uses locks to avoid concurrent write issues.

🧩 Ethical & Legal Notice ⚠️

⚠️ This code is for educational and experimental purposes only.
It is designed to study wallet derivation, HD key generation, and address structure in Bitcoin and similar cryptocurrencies.
You must use it only against your own addresses or datasets that you own or have explicit permission to analyze.

Scanning or probing other users’ wallets or attempting to recover unknown private keys is illegal and unethical.

The author takes no responsibility for misuse of this tool.
BTC donation address: bc1q4nyq7kr4nwq6zw35pg0zl0k9jmdmtmadlfvqhr
