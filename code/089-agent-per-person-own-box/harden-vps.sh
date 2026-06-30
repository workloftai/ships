#!/usr/bin/env bash
# Harden a fresh Ubuntu VPS that runs an AI agent: key-only SSH, a default-deny
# firewall, fail2ban, and automatic security updates. Idempotent. Run as root
# (or with sudo). Safe to re-run.
#
# WARNING: this disables SSH password login. Make sure your public key is in
# ~/.ssh/authorized_keys and a key-based login works BEFORE you run this, or you
# will lock yourself out. If you connect on a non-22 port, set SSH_PORT first.
set -uo pipefail

SSH_PORT="${SSH_PORT:-22}"

echo "[1/4] SSH hardening (key-only)"
install -d -m 0755 /etc/ssh/sshd_config.d
# 00- prefix so this wins over a 50-cloud-init.conf that ships PasswordAuthentication yes
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<CONF
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin prohibit-password
KbdInteractiveAuthentication no
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
CONF
# Belt and braces: blank out any other drop-in that re-enables password auth.
grep -rliE '^PasswordAuthentication yes' /etc/ssh/sshd_config.d/ 2>/dev/null \
  | grep -v 00-hardening | while read -r f; do
    sed -i 's/^PasswordAuthentication yes/PasswordAuthentication no/I' "$f"
  done
if sshd -t; then
  systemctl reload ssh 2>/dev/null || systemctl reload sshd
  echo "  sshd config valid + reloaded"
else
  echo "  !! sshd -t FAILED, config NOT reloaded (you are safe, fix and re-run)"
fi

echo "[2/4] Firewall: allow SSH first, then default-deny incoming"
apt-get install -y ufw >/dev/null 2>&1
ufw allow "${SSH_PORT}"/tcp >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw --force enable >/dev/null
echo "  $(ufw status | head -1)"

echo "[3/4] fail2ban (ban repeat SSH offenders)"
DEBIAN_FRONTEND=noninteractive apt-get install -y fail2ban >/dev/null 2>&1
cat > /etc/fail2ban/jail.local <<CONF
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
CONF
systemctl enable --now fail2ban >/dev/null 2>&1
echo "  fail2ban: $(systemctl is-active fail2ban)"

echo "[4/4] Automatic security updates"
DEBIAN_FRONTEND=noninteractive apt-get install -y unattended-upgrades >/dev/null 2>&1
systemctl enable --now unattended-upgrades >/dev/null 2>&1
echo "  unattended-upgrades: $(systemctl is-active unattended-upgrades)"

echo
echo "Done. Verify with:"
echo "  sshd -T | grep -E 'passwordauthentication|permitrootlogin|x11forwarding'"
echo "  ufw status verbose | head"
echo "  systemctl is-active fail2ban unattended-upgrades"
