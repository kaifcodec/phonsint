# phonsint
<img width="1713" height="420" alt="phonsint-banner" src="https://github.com/user-attachments/assets/a76a73a2-8aac-4813-a265-6802b2230eb0" />

<p align="center">
  <img src="https://img.shields.io/badge/Version-0.1.0-blueviolet?style=for-the-badge&logo=github" />
  <img src="https://img.shields.io/badge/Tested%20on-Linux%20%7C%20macOS%20%7C%20Windows%20%7C%20Termux-black?style=for-the-badge" />
</p>

<p align="center">
  <strong>High-Throughput Silent Phone Number OSINT & Identity Footprinting Suite</strong><br>
  <em>Uncover account registrations, masked emails, display names, and profile photos across major platforms—without ever dispatching an SMS or alerting the target.</em>
</p>

---

## ⚡ What is phonsint?

Most phone number tools stop at basic format parsing or risk blowing an investigation by triggering loud 2FA/SMS verification codes to the target's mobile device.

**phonsint** is engineered for **silent, high-fidelity reconnaissance**. It interrogates pre-authentication discovery endpoints, recovery validation flows, and cryptographic challenge APIs (such as Meta LOX proof-of-work) to determine account existence and extract rich profile metadata—**completely silently**.

---

## ✨ Key Capabilities

* **Guaranteed Silent Operation**: Exploits unauthenticated query endpoints and pre-dispatch recovery flows that **never send SMS verification codes or push notifications** to the target.
* **Deep Identity Enrichment**:
  * 📧 **Masked Email Addresses**: Surfaces linked emails (e.g. `j******e@gmail.com`) associated with the phone number.
  * 👤 **Full Display Names**: Pulls account owner names from public platform recovery APIs.
  * 🖼️ **High-Resolution Avatars**: Extracts direct CDN profile photo URLs without logging in.
  * 🏢 **Tenant & Region Routing**: Identifies regional datacenters (e.g., Zoho US, EU, IN, CN, JP).
* **High-Throughput Concurrency**: Built with Python `asyncio` and `curl_cffi` for browser TLS fingerprint impersonation (bypasses Cloudflare, Akamai, and Shape Security without heavy headless browsers).
* **Zero False Positives**: Uses strict, dual-state validation markers (matching the design philosophy of [`user-scanner`](https://github.com/kaifcodec/user-scanner)).
*  **Multi-Format Reports**: Automated structured exports to **JSON** and **CSV** for immediate ingestion into investigation pipelines.

---

## 🖥️ Live Terminal Preview

```text
Checking phone: +14155552671

== SOCIAL SITES ==
[✔] Facebook (+14155552671) [Registered]
    ├── name: John Doe
    ├── masked_email: j******e@gmail.com
    └── avatar: https://scontent.xx.fbcdn.net/v/t39.30808-1/s200x200/412...

[✔] Instagram (+14155552671) [Registered]
    └── contact_point: Phone Number Verified

== AUTH SITES ==
[✔] Microsoft (+14155552671) [Registered]
    └── auth_type: Live ID / Account Exists

== SHOPPING SITES ==
[✔] Amazon (+14155552671) [Registered]
    └── claim_endpoint: Active Sign-in Route

== SUMMARY ==
Total Sites Scanned: 5
Registered / Found:  4
```

---

## 📋 Structured JSON Output Example

When exported using `-o output.json`, `phonsint` formats rich metadata into clean, structured JSON ready for Maltego, identity graphs, or analysis pipelines:

```json
[
  {
    "site_name": "Facebook",
    "category": "Social",
    "phone": "+14155552671",
    "status": "Registered",
    "url": "https://www.facebook.com/login/identify",
    "extra": {
      "name": "John Doe",
      "masked_email": "j******e@gmail.com"
    },
    "media": {
      "avatar": "https://scontent.xx.fbcdn.net/v/t39.30808-1/s200x200/41208912_photo.jpg"
    },
    "reason": null
  },
  {
    "site_name": "Instagram",
    "category": "Social",
    "phone": "+14155552671",
    "status": "Registered",
    "url": "https://www.instagram.com/accounts/password/reset/",
    "extra": {
      "contact_point": "Phone Number Verified"
    },
    "media": {},
    "reason": null
  },
  {
    "site_name": "Microsoft",
    "category": "Auth",
    "phone": "+14155552671",
    "status": "Registered",
    "url": "https://login.live.com",
    "extra": {
      "throttle_status": 0
    },
    "media": {},
    "reason": null
  }
]
```

---

## 🚀 Installation

### 🐍 Via Virtual Environment (Recommended)

```bash
# Clone the repository
git clone https://github.com/kaifcodec/phonsint.git
cd phonsint

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1

# Install dependencies and package in editable mode
pip install -e .
```

### 📦 Direct Installation

```bash
pip install phonsint
```

---

## 💻 Usage Guide

### 1. Standard Target Scan (E.164 Format)

```bash
phonsint -p +14155552671
```

### 2. Scanning Local Format Numbers with Default Region

If a target number does not include an international `+` country prefix, specify the default ISO country code:

```bash
phonsint -p 07911123456 -r GB
phonsint -p 9876543210 -r IN
```

### 3. Targeted Category & Module Filtering

```bash
# Scan authentication providers only (e.g., Microsoft)
phonsint -p +14155552671 -c auth

# Scan specific platforms
phonsint -p +14155552671 -m facebook,instagram

# List all available modules and categories in a clean table
phonsint -l
```

### 4. Verbose Mode & Exporting Results

```bash
# Show all results including unregistered platforms and diagnostic reasons
phonsint -p +14155552671 --all -v

# Export results to JSON or CSV
phonsint -p +14155552671 -o report.json
phonsint -p +14155552671 -f csv -o report.csv
```

---

## 🛡️ OPSEC & Silent-by-Default Guarantee

In phone OSINT, accidental SMS verification codes sent to the target's phone are a critical operational failure. `phonsint` operates **100% silently by default**, targeting pre-dispatch query endpoints, session credential checks, and unauthenticated recovery validations that **do not dispatch SMS messages**.

Any module that could potentially trigger a notification is registered under `LOUD_MODULES` in `phonsint/core/helpers.py` and will be automatically skipped unless the user explicitly passes `--allow-loud`.

---

## 🤝 Contributing

We welcome contributions! Adding a new platform check takes around ~30 lines of clean Python. Check out **[CONTRIBUTING.md](CONTRIBUTING.md)** for developer conventions, validator signatures, and instructions.

---

## 📜 License

Distributed under the **MIT License**.
