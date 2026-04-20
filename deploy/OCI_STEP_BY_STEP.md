# OCI Step-by-Step Deployment Guide

This guide is for a single OCI Linux VM that runs the project in `armed` mode.
It is intended for:

- dashboard
- dryrun
- Telegram bot
- Polymarket API probe
- API execution preview

It is not a `live` trading guide.

## 0. Before You Start

You need:

- an OCI account
- a Linux VM in your OCI tenancy
- an SSH key pair on your laptop
- this repository URL
- your Telegram bot token and chat ID
- your Polymarket API credentials stored only on the server

Relevant Oracle docs:

- [Always Free Resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
- [Regions and Availability Domains](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/regions.htm)
- [Oracle Public Cloud Regions](https://www.oracle.com/cloud/public-cloud-regions/)
- [Launch Your First Linux Instance](https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm)
- [Accessing an Instance](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/accessinginstance.htm)
- [Security Lists](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securitylists.htm)
- [Security Rules](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/securityrules.htm)

## 1. Pick the Right OCI Account / Region

If you want `Always Free` resources in Canada, your tenancy `home region` must
be a Canada region.

What to check in the OCI Console:

1. Sign in to OCI.
2. Check the region picker in the top bar.
3. Confirm your tenancy home region is:
   - `Canada Southeast (Toronto)`, or
   - `Canada Southeast (Montreal)`

If your home region is not Canada:

- you can still deploy the project
- but the "free + Canada" plan is no longer the same plan

## 2. Create the VM in the OCI Console

Go to:

- `Compute`
- `Instances`
- `Create instance`

Recommended settings:

1. Name
   - `polymarket-auto-trader`

2. Placement
   - keep the default availability domain

3. Image and shape
   - Image: Ubuntu 22.04 or Ubuntu 24.04
   - Shape: choose an `Always Free eligible` shape if available

4. Networking
   - use the default VCN/subnet if this is your first OCI VM
   - assign a public IPv4 address

5. SSH keys
   - upload your public key
   - or let OCI generate one and download it

6. Boot volume
   - `40 GB` is enough

Create the instance and wait until it becomes `Running`.

## 3. Open Only the Ports You Need

You need:

- `22/tcp` for SSH
- `8787/tcp` for the dashboard

Do this in OCI networking/security rules.

Safer option:

- allow `22` only from your home/work IP
- allow `8787` only from your own IP first

Do not open `8787` to the whole internet unless you really need it.

## 4. SSH into the VM

From your laptop:

```bash
ssh -i ~/.ssh/<your-private-key> ubuntu@<your-server-ip>
```

If the default user is not `ubuntu`, use the user OCI shows for that image.

## 5. Install Base Packages

Run on the server:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
```

Optional but useful:

```bash
sudo apt install -y jq
```

## 6. Clone the Repo

```bash
git clone <your-repo-url> polymarket-auto-trader
cd polymarket-auto-trader
```

If the repo is private, use the access method you normally use:

- SSH
- GitHub token
- another git remote credential flow

## 7. Create the Python Environment

```bash
python3 -m venv ~/.signal-deck/venv
source ~/.signal-deck/venv/bin/activate
python -m pip install --upgrade pip
pip install py-clob-client eth-account
```

This is enough for the current project state:

- dashboard uses the standard library
- probe needs `py-clob-client`
- auth/signing needs `eth-account`

## 8. Prepare Runtime Directories

```bash
mkdir -p ~/.signal-deck/runtime
mkdir -p ~/.signal-deck/logs
```

## 9. Copy the Example Env Files

From the repo root:

```bash
cp deploy/polymarket.env.example ~/.signal-deck/runtime/polymarket.env
cp deploy/telegram.env.example ~/.signal-deck/runtime/telegram.env
```

## 10. Fill in `polymarket.env`

Edit:

```bash
nano ~/.signal-deck/runtime/polymarket.env
```

Set:

```bash
export SIGNAL_DECK_EXECUTION_MODE="armed"
export POLYMARKET_CLOB_HOST="https://clob.polymarket.com"
export POLYMARKET_CHAIN_ID="137"
export POLYMARKET_SIGNATURE_TYPE="0"
export POLYMARKET_RELAYER_HOST="https://relayer-v2.polymarket.com"

export POLYMARKET_PRIVATE_KEY="YOUR_PRIVATE_KEY"
export POLYMARKET_PROXY_ADDRESS="YOUR_PROXY_OR_FUNDER_ADDRESS"

export POLYMARKET_API_KEY=""
export POLYMARKET_API_SECRET=""
export POLYMARKET_API_PASSPHRASE=""

export POLYMARKET_RELAYER_API_KEY="YOUR_RELAYER_KEY_IF_USED"
export POLYMARKET_RELAYER_API_KEY_ADDRESS="YOUR_RELAYER_ADDRESS_IF_USED"
```

Leave the execution mode as `armed`.

Do not switch to `live`.

## 11. Fill in `telegram.env`

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

## 12. Run the Read-Only Polymarket Probe

From the repo root:

```bash
source ~/.signal-deck/venv/bin/activate
python3 probe_polymarket_api.py --persist-api-creds
```

What this should do:

- verify CLOB connectivity
- verify wallet-based auth
- derive or persist API creds
- write a probe result file

Expected output file:

```bash
~/.signal-deck/logs/polymarket_probe.json
```

If this fails, stop here and fix auth before installing services.

## 13. Install the Background Services

From the repo root:

```bash
SIGNAL_DECK_DASHBOARD_HOST=0.0.0.0 \
SIGNAL_DECK_DASHBOARD_PORT=8787 \
SIGNAL_DECK_LOOP_INTERVAL=5 \
PYTHON_BIN=$HOME/.signal-deck/venv/bin/python \
./install_linux_services.sh
```

This installs 3 `systemd --user` services:

- `polymarket-autotrader-dashboard.service`
- `polymarket-autotrader-dryrun.service`
- `polymarket-autotrader-telegrambot.service`

## 14. Make User Services Survive Logout

Run:

```bash
loginctl enable-linger "$USER"
```

Then verify:

```bash
systemctl --user daemon-reload
systemctl --user status polymarket-autotrader-dashboard.service
systemctl --user status polymarket-autotrader-dryrun.service
systemctl --user status polymarket-autotrader-telegrambot.service
```

## 15. Verify the Deployment

Check the dashboard:

```text
http://<your-server-ip>:8787/
```

Check health:

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=10).read().decode())
PY
```

Check the execution API:

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:8787/api/execution/latest', timeout=10).read().decode()[:1200])
PY
```

Check Telegram command bot:

- send `/status`
- send `/botstatus`

## 16. Where to Look If Something Breaks

Main logs:

```bash
tail -n 100 ~/.signal-deck/logs/dryrun_launchd.log
tail -n 100 ~/.signal-deck/logs/telegram_bot.log
tail -n 100 ~/.signal-deck/logs/polymarket_probe.json
tail -n 100 ~/.signal-deck/logs/polymarket_execution.csv
```

Service status:

```bash
systemctl --user status polymarket-autotrader-dashboard.service
systemctl --user status polymarket-autotrader-dryrun.service
systemctl --user status polymarket-autotrader-telegrambot.service
```

Service restart:

```bash
systemctl --user restart polymarket-autotrader-dashboard.service
systemctl --user restart polymarket-autotrader-dryrun.service
systemctl --user restart polymarket-autotrader-telegrambot.service
```

## 17. What "Success" Looks Like

You should end up with:

- dashboard reachable on port `8787`
- Telegram bot responding
- dryrun running every 5 seconds
- probe JSON present
- execution preview visible in the UI
- execution mode still set to `armed`

## 18. What You Should Not Do Yet

Do not do these yet:

- do not set `SIGNAL_DECK_EXECUTION_MODE="live"`
- do not assume server location alone makes Polymarket live trading allowed
- do not store secrets in the repo
- do not expose the dashboard port broadly unless needed

## 19. If You Want the Simplest Daily Workflow

After deployment, the normal workflow is:

1. SSH in only when you need maintenance
2. Watch the dashboard in browser
3. Use Telegram for alerts and status
4. Keep the server in `armed`
5. Use the probe and execution preview as your go/no-go signal
