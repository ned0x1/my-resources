# Linux Post-Exploitation & Privilege Escalation

---

## Upgrade to a Proper Shell

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
````

Spawns an interactive TTY with job control and tab completion.

```bash
stty raw -echo; fg
export TERM=xterm-256color
```

Fixes a broken terminal after backgrounding the shell.

---

## User & Privilege Enumeration

```bash
whoami
id
groups
```

Identifies the current user, UID/GID, and group memberships.

```bash
sudo -l
```

Lists commands the user can run as root (often instant privilege escalation).

```bash
sudo su
sudo -i
```

Attempts to obtain a full root shell.

---

## Environment & Context

```bash
hostname
pwd
ls -la
```

Provides system context and file visibility.

```bash
env
echo $PATH
```

Checks for sensitive environment variables and PATH abuse opportunities.

---

## Running Processes & Services

```bash
ps aux
ps aux | grep root
```

Identifies processes running as root.

```bash
ss -lntup
netstat -tulnp
```

Lists listening network services (often internal-only services).

---

## File & Directory Permissions

```bash
find / -writable -type f 2>/dev/null
```

Finds writable files that may allow configuration or script hijacking.

```bash
find / -writable -type d 2>/dev/null
```

Finds writable directories useful for PATH or cron abuse.

---

## SUID & SGID Binaries

```bash
find / -perm -4000 -type f 2>/dev/null
```

Lists SUID binaries that execute with root privileges.

```bash
find / -perm -2000 -type f 2>/dev/null
```

Lists SGID binaries that execute with group privileges.

> Always cross-check findings on **GTFOBins**.

---

## Cron Jobs & Scheduled Tasks

```bash
crontab -l
```

Lists scheduled tasks for the current user.

```bash
cat /etc/crontab
```

Displays system-wide cron jobs (often executed as root).

```bash
ls -alh /etc/cron*
```

Shows hourly, daily, weekly, and monthly cron jobs.

```bash
ls -alh /var/spool/cron
ls -alh /var/spool/cron/crontabs
```

Displays per-user cron job storage.

**Look for:**

* Writable scripts
* Relative paths
* Wildcards (`*`)
* Jobs executed as **root**

---

## 8️⃣ OS & Kernel Information

```bash
uname -a
```

Displays kernel version information.

```bash
cat /proc/version
cat /etc/issue
cat /etc/*-release
```

Identifies the operating system and distribution.

> Use results with `searchsploit` or `linux-exploit-suggester`.

---

## Credential Hunting

```bash
grep -Ri "password" /etc 2>/dev/null
```

Searches configuration files for hardcoded passwords.

```bash
grep -Ri "password\|user\|pass" /var/www 2>/dev/null
```

Searches web application files for credentials.

```bash
cat ~/.bash_history
cat ~/.zsh_history
```

Checks shell history for sensitive commands or secrets.

---

## SSH Keys

```bash
ls -la ~/.ssh
```

Lists SSH configuration and key files.

```bash
cat ~/.ssh/id_rsa
```

Displays private SSH keys for potential lateral movement.

---

## Network & Internal Access

```bash
ip a
ip route
arp -a
```

Enumerates network interfaces, routes, and ARP cache.

---

## Linux Capabilities

```bash
getcap -r / 2>/dev/null
```

Lists binaries with Linux capabilities that may allow privilege escalation.

**Dangerous capabilities include:**

* `cap_setuid`
* `cap_sys_admin`
* `cap_dac_read_search`

---

## Docker & Container Escapes

```bash
cat /proc/1/cgroup
```

Checks if the system is running inside a container.

```bash
ls -l /var/run/docker.sock
```

Writable Docker socket often leads to immediate root access.

---

## Mounted Filesystems

```bash
mount
df -h
lsblk
```

Identifies mounted filesystems, backups, and shared storage.

```
