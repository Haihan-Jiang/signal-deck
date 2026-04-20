# Google Cloud Compute Engine Deployment Guide

This guide deploys the project to one Google Cloud Compute Engine VM.

It runs:

- dashboard
- dryrun
- Telegram bot
- Polymarket API probe
- API execution preview

It keeps execution mode at `armed`.

It does not enable real `live` order placement.

## 0. Important Cost / Region Reality

Google Cloud has two different "free" concepts:

1. `90-day, $300 Free Trial`
   - can be used in more regions while trial credits last

2. `Compute Engine Free Tier`
   - includes one `e2-micro` VM per month, but only in these US regions:
     - `us-west1` Oregon
     - `us-central1` Iowa
     - `us-east1` South Carolina

Official docs:

- [Google Cloud Free Program](https://cloud.google.com/free/docs/gcp-free-tier)
- [Compute Engine free features](https://cloud.google.com/free/docs/compute-getting-started)

If you want a Canada VM on GCP:

- use `northamerica-northeast1` Montreal, or
- use `northamerica-northeast2` Toronto

But Canada Compute Engine usage is usually not the long-term Compute Free Tier.
It may be covered by trial credits first, then become paid.

## 1. Recommended Architecture

For this project, use Compute Engine first.

Do not start with Cloud Run unless you want to refactor.

Reason:

- this app has a persistent dryrun loop
- Telegram bot uses long polling
- logs are local CSV / JSON files
- the existing installer already targets Linux `systemd --user`

Compute Engine is the clean lift-and-shift path.

## 2. Pick Region and Machine

If this is only for dashboard / dryrun / armed preview:

- cheapest acceptable VM is fine
- `e2-micro` can work, but it may be tight
- `e2-small` or `e2-medium` is more comfortable

Region choices:

- lowest cost / Free Tier: `us-west1`, `us-central1`, or `us-east1`
- Canada test: `northamerica-northeast1` or `northamerica-northeast2`

For live execution, do not assume region alone makes trading allowed.
You still need platform and account-level permission checks.

## 3. Create a Google Cloud Project

In Google Cloud Console:

1. Go to `IAM & Admin`
2. Go to `Manage resources`
3. Create or select a project
4. Link billing

Enable APIs:

- Compute Engine API

Docs:

- [Google Cloud Free Program](https://cloud.google.com/free/docs/gcp-free-tier)
- [Compute Engine regions and zones](https://cloud.google.com/compute/docs/regions-zones)

## 4. Create the VM from Console

Go to:

- `Compute Engine`
- `VM instances`
- `Create instance`

Recommended settings:

1. Name
   - `polymarket-auto-trader`

2. Region / zone
   - Free Tier test:
     - `us-west1`
     - `us-central1`
     - `us-east1`
   - Canada test:
     - `northamerica-northeast1`
     - `northamerica-northeast2`

3. Machine type
   - cheapest: `e2-micro`
   - smoother: `e2-small`

4. Boot disk
   - Ubuntu 22.04 LTS or Ubuntu 24.04 LTS
   - 30 GB standard persistent disk is enough

5. Firewall
   - allow SSH
   - do not blindly allow HTTP/HTTPS unless you need them

6. Network tags
   - add:
     - `polymarket-dashboard`

Create the VM.

## 5. Add Firewall Rule for Dashboard Port 8787

Safer option: allow only your IP.

Replace `YOUR_PUBLIC_IP` with your current public IP.

Using `gcloud`:

```bash
gcloud compute firewall-rules create allow-polymarket-dashboard-8787 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8787 \
  --source-ranges=YOUR_PUBLIC_IP/32 \
  --target-tags=polymarket-dashboard
```

If you need temporary broad access:

```bash
gcloud compute firewall-rules create allow-polymarket-dashboard-8787 \
  --direction=INGRESS \
  --priority=1000 \
  --network=default \
  --action=ALLOW \
  --rules=tcp:8787 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=polymarket-dashboard
```

Prefer the first version.

Docs:

- [VPC firewall rules](https://cloud.google.com/firewall/docs/firewalls)
- [Create a firewall rule](https://cloud.google.com/compute/docs/samples/compute-firewall-create)

## 6. SSH into the VM

From Google Cloud Console:

- click `SSH`

Or from your terminal:

```bash
gcloud compute ssh polymarket-auto-trader --zone <ZONE>
```

Example:

```bash
gcloud compute ssh polymarket-auto-trader --zone northamerica-northeast1-a
```

Docs:

- [Connect to Linux VMs](https://cloud.google.com/compute/docs/connect/standard-ssh)

## 7. Install Base Packages

Run on the VM:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

Optional:

```bash
sudo apt install -y jq
```

## 8. Clone the Repo

```bash
git clone <your-repo-url> polymarket-auto-trader
cd polymarket-auto-trader
```

If the repo is private, use your normal private repo access method:

- SSH deploy key
- GitHub token
- GitHub CLI

## 9. Create Python Virtualenv

```bash
python3 -m venv ~/.signal-deck/venv
source ~/.signal-deck/venv/bin/activate
python -m pip install --upgrade pip
pip install py-clob-client eth-account
```

## 10. Prepare Runtime Directories

```bash
mkdir -p ~/.signal-deck/runtime
mkdir -p ~/.signal-deck/logs
```

## 11. Copy Runtime Env Templates

From repo root:

```bash
cp deploy/polymarket.env.example ~/.signal-deck/runtime/polymarket.env
cp deploy/telegram.env.example ~/.signal-deck/runtime/telegram.env
```

## 12. Configure Polymarket Env

Edit:

```bash
nano ~/.signal-deck/runtime/polymarket.env
```

Keep:

```bash
export SIGNAL_DECK_EXECUTION_MODE="armed"
```

Fill the credential values only on the server.

Do not commit this file.

Do not switch to `live`.

## 13. Configure Telegram Env

Edit:

```bash
nano ~/.signal-deck/runtime/telegram.env
```

Set:

```bash
export SIGNAL_DECK_TELEGRAM_BOT_TOKEN="YOUR_BOT_TOKEN"
export SIGNAL_DECK_TELEGRAM_CHAT_ID="YOUR_PERSONAL_CHAT_ID"
export SIGNAL_DECK_TELEGRAM_CHAT_IDS="YOUR_PERSONAL_CHAT_ID,OPTIONAL_GROUP_ID"
export SIGNAL_DECK_TELEGRAM_BOT_USERNAME="YOUR_BOT_USERNAME"
```

## 14. Run Read-Only Probe

```bash
source ~/.signal-deck/venv/bin/activate
python3 probe_polymarket_api.py --persist-api-creds
```

Expected output file:

```bash
~/.signal-deck/logs/polymarket_probe.json
```

If probe fails, stop here.

Do not install live execution.

## 15. Install Background Services

From repo root:

```bash
SIGNAL_DECK_DASHBOARD_HOST=0.0.0.0 \
SIGNAL_DECK_DASHBOARD_PORT=8787 \
SIGNAL_DECK_LOOP_INTERVAL=5 \
PYTHON_BIN=$HOME/.signal-deck/venv/bin/python \
./install_linux_services.sh
```

This installs:

- `polymarket-autotrader-dashboard.service`
- `polymarket-autotrader-dryrun.service`
- `polymarket-autotrader-telegrambot.service`

## 16. Keep User Services Running After Logout

Run:

```bash
loginctl enable-linger "$USER"
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user status polymarket-autotrader-dashboard.service
systemctl --user status polymarket-autotrader-dryrun.service
systemctl --user status polymarket-autotrader-telegrambot.service
```

## 17. Verify Locally on the VM

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=10).read().decode())
PY
```

Expected:

```json
{"ok": true}
```

Check execution latest:

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8787/api/execution/latest', timeout=10).read().decode()[:1200])
PY
```

## 18. Open Dashboard from Browser

Use:

```text
http://<VM_EXTERNAL_IP>:8787/
```

If it does not open:

1. Check firewall rule target tag
2. Check VM has tag `polymarket-dashboard`
3. Check service:

```bash
systemctl --user status polymarket-autotrader-dashboard.service
```

4. Check local health from VM:

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=10).read().decode())
PY
```

## 19. Check Logs

```bash
tail -n 100 ~/.signal-deck/logs/dryrun_launchd.log
tail -n 100 ~/.signal-deck/logs/telegram_bot.log
tail -n 100 ~/.signal-deck/logs/polymarket_execution.csv
tail -n 100 ~/.signal-deck/logs/polymarket_probe.json
```

## 20. Restart Services

```bash
systemctl --user restart polymarket-autotrader-dashboard.service
systemctl --user restart polymarket-autotrader-dryrun.service
systemctl --user restart polymarket-autotrader-telegrambot.service
```

## 21. Normal Operating Mode

Expected final state:

- dashboard reachable on `8787`
- Telegram bot responds to `/status` and `/botstatus`
- dryrun loop runs every `5s`
- API execution preview shows `armed`
- no live orders are submitted

## 22. What Not To Do Yet

Do not:

- set `SIGNAL_DECK_EXECUTION_MODE="live"`
- store private keys in git
- expose dashboard to `0.0.0.0/0` permanently
- assume Canada or US server location alone makes live trading compliant

## 23. If You Want Canada on GCP

Use:

- `northamerica-northeast1` for Montreal
- `northamerica-northeast2` for Toronto

But remember:

- GCP Compute Engine long-term Free Tier is US-region only
- Canada VM may use trial credit first and become paid later
- live trading still requires platform/account eligibility checks
