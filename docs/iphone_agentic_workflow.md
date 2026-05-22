# Zero-Cost iPhone Agentic Workflow

This workflow is designed for the real iOS boundary: the iPhone can trigger
Shortcuts automations and call URLs, but it cannot silently operate arbitrary
third-party apps, bypass login or CAPTCHA screens, or give legal/financial
consent for you. The no-cost version therefore uses the iPhone as the control
surface and a local Mac LaunchAgent as the always-on executor and scheduler.

## What Runs With No Intervention

- Daily job candidate scoring, answer drafting, closed-posting checks, local
  outbox writes, and Telegram notification through `job_apply_agent`.
- A lightweight phone-readable status heartbeat from local logs and outbox
  files.
- Signal Deck dry-run snapshots through `dryrun_recorder.py` when manually
  triggered from the phone. Keep this manual by default because this task relies
  on external sports/market network calls; the repo's existing dry-run daemon is
  the better always-on path for Signal Deck.
- Any additional local command you explicitly add to
  `~/.signal-deck/runtime/iphone_agent_config.json`.

## What Still Requires Consent

- Submitting real job applications, especially forms with identity, legal,
  immigration, compensation, or equal-opportunity attestations.
- Login, two-factor authentication, CAPTCHA, or anti-bot flows.
- Live financial orders. The included Signal Deck action is dry-run only.
- Anything that requires iOS to control another app in the background.

## Setup

From the repo root:

```bash
cd "/Users/haihan/Documents/New project"
./install_iphone_agent_launchd.sh
```

The installer creates:

- `~/.signal-deck/runtime/iphone_agent_app/`
- `~/.signal-deck/runtime/iphone_agent_config.json`
- `~/Library/LaunchAgents/com.haihan.signaldeck.iphoneagent.plist`
- `~/.signal-deck/logs/iphone_agent.log`
- `~/.signal-deck/logs/iphone_agent_runs.jsonl`

The app code is copied into `~/.signal-deck/runtime/iphone_agent_app/` so the
LaunchAgent can run without needing background access to the `Documents`
folder.

The LaunchAgent also ticks the scheduler every 60 seconds by default. Scheduled
tasks can therefore run unattended from the Mac even if you do not open the
iPhone web app. The iPhone app and Shortcuts URLs are still useful for status,
manual triggers, NFC/app/time automations, and recovery.

Verify the live setup:

```bash
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json doctor
```

Print the same-Wi-Fi URL for the iPhone:

```bash
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json shortcut-url
```

Open the printed URL in iPhone Safari, then use Share -> Add to Home Screen.
That gives you a no-cost iPhone app-like control surface.

## iPhone Shortcuts Automation

Create one Personal Automation in Shortcuts:

1. Open Shortcuts -> Automation -> New Automation.
2. Choose Time of Day, such as 5:00 PM.
3. Add action: Get Contents of URL.
4. Paste the URL from:

   ```bash
   python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json shortcut-url
   ```

5. Set the automation to run without asking when iOS offers that option.

Use a per-task URL when you want a specific button or NFC trigger:

```bash
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json shortcut-url --task job_drafts_daily
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json shortcut-url --task signal_snapshot
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json shortcut-url --task status_snapshot
```

Apple's Shortcuts guide confirms that Personal Automations can be triggered by
events such as time of day, location, app opening, Wi-Fi, Bluetooth, battery,
and NFC, and that some automations can run without asking. See:

- https://support.apple.com/guide/shortcuts/intro-to-personal-automation-apd690170742/ios
- https://support.apple.com/guide/shortcuts/enable-or-disable-a-personal-automation-apd602971e63/ios

## Adding More Zero-Cost Tasks

Edit `~/.signal-deck/runtime/iphone_agent_config.json` and add a task:

```json
{
  "id": "example_local_task",
  "title": "Example local task",
  "enabled": true,
  "unattended": true,
  "schedule": { "kind": "daily", "time": "08:30" },
  "ios_boundary": "Runs a local command only. No paid API calls.",
  "action": {
    "kind": "argv",
    "cwd": "{repo}",
    "timeout_seconds": 120,
    "argv": ["{python}", "-c", "print('done')"]
  }
}
```

Then call:

```bash
python3 ~/.signal-deck/runtime/iphone_agent_app/iphone_agent.py --config ~/.signal-deck/runtime/iphone_agent_config.json status
```

The scheduler supports these task schedules:

- `{"kind": "daily", "time": "HH:MM"}`
- `{"kind": "interval", "minutes": 30}`
- `{"kind": "manual"}`

The Mac-side scheduler itself is controlled by the top-level config:

```json
{
  "no_cost": true,
  "scheduler": { "enabled": true, "tick_seconds": 60 },
  "policy": {
    "allow_paid_services": false,
    "allow_llm_api_calls": false,
    "external_submit_requires_explicit_confirmation": true
  }
}
```

## Security Boundary

The local server uses a random token in the URL. Keep it on trusted Wi-Fi. If
you expose the server beyond your home network, use a private VPN or tunnel
that you control and keep the token required.
