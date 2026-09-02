# UNIKEY Farmer

Multi-thread Web3 wallet farmer untuk **getunikey.ai** (new-api fork) — register wallet → create API key → precheck validity. Pure HTTP, zero browser.

> ⚠️ Educational/research purposes only. Gunakan di target milik sendiri atau yang kamu punya izin.

## Pipeline

```
wallet baru → challenge → EIP-191 sign → Turnstile → verify
    → uid → create token → reveal key → precheck /v1 → VALID
```

- Register = auto-create account (bonus 500,000 quota / wallet)
- API key full hanya via `POST /api/token/{id}/key` (list API mask key)
- Precheck = chat completion prompt `hi` via `/v1/chat/completions`

## Struktur

```
unikey-farmer/
├── main.py        entry: CLI interaktif + multi-thread worker
├── client.py      UnikeyClient (register → apikey → precheck)
├── solver.py      Capsolver Turnstile solver
├── proxy.py       load/check proxy.txt, assign per worker
├── config.py      .env loader
├── logsetup.py    loguru custom format
├── .env.example   config template
└── proxy.txt.template   proxy template
```

## Setup

```bash
pip install curl_cffi eth_account loguru python-dotenv

cp .env.example .env        # isi CAPSOLVER_KEY
cp proxy.txt.template proxy.txt   # isi proxy list
```

Isi `.env` minimal:
```
CAPSOLVER_KEY=CAP-xxxxx
```

## Run

```bash
python main.py
```

Interactive:
```
Mau berapa akun? [5]: 100
Berapa thread worker? [3]: 10
Mode proxy: [r]andom unique / [s]equential / enter=auto →
```

Worker = thread, tiap worker wajib pakai proxy unik (rate-limit per-IP).

## Output

`output/accounts.json` — auto-merge tiap run:

```json
{
  "address": "0xYourWalletAddressHere",
  "private_key": "0xyour64hexprivatekey",
  "uid": 123456,
  "username": "wallet_0xYourAddr",
  "api_key": "sk-your-api-key",
  "quota": 500000,
  "valid": true,
  "status": "VALID",
  "proxy": "http://…",
  "registered_at": "2026-09-02T15:53:25"
}
```

## Catatan Penting

- **Rate limit per-IP**: ~6 register / 10–15 menit. Kena 429 = kosong body (handle HTTP code, bukan parse JSON).
- **Turnstile** solve via Capsolver `AntiTurnstileTaskProxyLess` — token TIDAK IP-bound.
- **Model mapping**: `gemini-3.5-flash` → dipetakan ke `pro` (lambat, bisa 524). Pakai `flash-lite` untuk health check.
- Fail rate normal ~15% (proxy timeout / rate limit). Re-run untuk catch-up.

## Benchmark

| Config | Hasil | Waktu |
|---|---|---|
| 100 akun / 10 worker / residential proxy | 84 valid, 16 fail | ~16 menit |

## License

MIT
