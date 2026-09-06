# Raspberry Pi Operations Cheat Sheet

This document collects the commands used regularly to develop Bundestag Pulse on the laptop and run it on the Raspberry Pi.

The examples assume:

```text
Pi user: luca
Pi hostname: poliwatch
Repository: /home/luca/apps/poliwatch
Generated site: /srv/poliwatch/site
Service: poliwatch-update.service
```

## Normal development and deployment

On the laptop, after making and testing changes:

```bash
git status
git add <changed-files>
git commit -m "Describe the change"
git push origin main
```

Using explicit filenames with `git add` avoids accidentally committing local files such as `.env.local` or unrelated work.

Deploy the code to the Pi:

```bash
ssh luca@poliwatch.local
cd /home/luca/apps/poliwatch
git pull --ff-only origin main
```

`--ff-only` refuses unexpected merges if the Pi's checkout has diverged from `origin/main`.

## Run an update and watch it live

Use this for an interactive update:

```bash
sudo systemctl start --no-block poliwatch-update.service \
  && sudo journalctl -fu poliwatch-update.service
```

Press `Ctrl-C` to stop watching the log. This does not stop the build.

Check whether the build succeeded:

```bash
sudo systemctl status poliwatch-update.service --no-pager
```

A successful build should show something like:

```text
status=0/SUCCESS
```

A crash normally shows:

```text
Failed with result 'exit-code'
```

## Inspect logs

Show the latest 100 log lines:

```bash
sudo journalctl -u poliwatch-update.service -n 100 --no-pager
```

Follow logs from an already-running build:

```bash
sudo journalctl -fu poliwatch-update.service
```

Show logs from the current boot only:

```bash
sudo journalctl -b -u poliwatch-update.service --no-pager
```

## Check the automatic schedule

Show the next and previous scheduled runs:

```bash
systemctl list-timers poliwatch-update.timer
```

Check the timer's state:

```bash
systemctl status poliwatch-update.timer --no-pager
```

Enable and start the timer:

```bash
sudo systemctl enable --now poliwatch-update.timer
```

Temporarily stop automatic updates:

```bash
sudo systemctl stop poliwatch-update.timer
```

Start automatic updates again:

```bash
sudo systemctl start poliwatch-update.timer
```

## Change how many sessions are processed

Edit the service:

```bash
sudo nano /etc/systemd/system/poliwatch-update.service
```

The `ExecStart` line controls the build:

```ini
ExecStart=/usr/bin/python3 scripts/build_dip_pulse_site.py --output-dir /srv/poliwatch/site --limit 0 --detail-limit 20 --preserve-existing-dossiers --summary-mode reuse
```

Useful values:

```text
--detail-limit 5     newest 5 detailed sessions
--detail-limit 20    newest 20 detailed sessions
--detail-limit 40    newest 40 detailed sessions
--detail-limit -1    generate no new dossiers
--detail-limit 0     generate every available dossier -- potentially thousands
```

After editing a systemd unit file, make systemd reload it:

```bash
sudo systemctl daemon-reload
```

Then run and observe the updated service:

```bash
sudo systemctl start --no-block poliwatch-update.service \
  && sudo journalctl -fu poliwatch-update.service
```

Always retain:

```text
--preserve-existing-dossiers
```

Without it, a narrow update can remove older dossiers from the rendered site and SQLite store.

## Process one specific session

From the Pi repository:

```bash
cd /home/luca/apps/poliwatch

python3 scripts/build_dip_pulse_site.py \
  --output-dir /srv/poliwatch/site \
  --limit 0 \
  --detail-limit -1 \
  --dossier-document-number 21/90 \
  --preserve-existing-dossiers \
  --summary-mode reuse
```

Replace `21/90` with the desired document number.

Unlike `--document-number`, `--dossier-document-number` adds a dossier without restricting the complete catalog to that one session.

## Run directly without systemd

This is useful for troubleshooting:

```bash
cd /home/luca/apps/poliwatch

python3 scripts/build_dip_pulse_site.py \
  --output-dir /srv/poliwatch/site \
  --limit 0 \
  --detail-limit 20 \
  --preserve-existing-dossiers \
  --summary-mode reuse
```

This displays progress directly in the terminal. Closing the SSH connection may terminate it, so systemd is preferable for normal builds.

## Run the tests

On the Pi:

```bash
cd /home/luca/apps/poliwatch
python3 -m unittest discover -s tests -v
```

On the laptop, run the same test command from the local repository root.

## Access the website

Preferred hostname:

```text
http://poliwatch.local/
```

Find the Pi's IP address if the hostname does not work:

```bash
hostname -I
```

Then open the reported address, for example:

```text
http://192.168.178.42/
```

## nginx checks

Validate the nginx configuration:

```bash
sudo nginx -t
```

Check whether nginx is running:

```bash
systemctl status nginx --no-pager
```

Reload nginx after changing its configuration:

```bash
sudo systemctl reload nginx
```

Restart nginx if necessary:

```bash
sudo systemctl restart nginx
```

Test nginx locally from the Pi:

```bash
curl -I http://127.0.0.1/
```

A healthy response should contain:

```text
HTTP/1.1 200 OK
Server: nginx
```

Confirm that the generated homepage exists:

```bash
ls -lh /srv/poliwatch/site/index.html
```

## Configuration reference

### nginx site

The nginx configuration is stored at `/etc/nginx/sites-available/poliwatch`:

```nginx
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    root /srv/poliwatch/site;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

### Update service

The service is stored at `/etc/systemd/system/poliwatch-update.service`:

```ini
[Unit]
Description=Update the Bundestag Pulse static site
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=luca
WorkingDirectory=/home/luca/apps/poliwatch
EnvironmentFile=/home/luca/apps/poliwatch/.env.local
ExecStart=/usr/bin/python3 scripts/build_dip_pulse_site.py --output-dir /srv/poliwatch/site --limit 0 --detail-limit 20 --preserve-existing-dossiers --summary-mode reuse
PrivateTmp=true
NoNewPrivileges=true
```

### Update timer

The timer is stored at `/etc/systemd/system/poliwatch-update.timer`:

```ini
[Unit]
Description=Update Bundestag Pulse every morning

[Timer]
OnCalendar=*-*-* 06:15:00
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

`Persistent=true` runs one catch-up update if the Pi was off at the scheduled time.
