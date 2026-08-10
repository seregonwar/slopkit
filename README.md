# slopkit

Credit: Egy, Sonic, Yenyen, Zeco, Gezine, Echostretch, Ufm42, TheFloW, John Tornblom, Flatz and PS5 R&D Discord.

![AI bell curve](readme.png)

## Payloads

The kit serves these payloads from `payloads/` after the jailbreak (via elfldr on port 9021):

| File | Payload | Source |
| --- | --- | --- |
| `zftpd-ps5.elf` | zftpd FTP server (replaces the legacy `ftpsrv-ps5.elf`) | [seregonwar/zftpd](https://github.com/seregonwar/zftpd) |
| `zftpd-ps5-zhttp.elf` | zftpd FTP + web file explorer (zhttp, ~3.8 MiB) | [seregonwar/zftpd](https://github.com/seregonwar/zftpd) |
| `MemDBG-ps5.elf` | MemDBG memory debugger / trainer daemon | [seregonwar/MemDBG](https://github.com/seregonwar/MemDBG) |
| `gdbsrv-ps5.elf`, `klogsrv-ps5.elf`, `shsrv-ps5.elf`, `websrv-ps5.elf` | bundled legacy payloads | n/a |

## Keeping payloads up to date

`tools/update_payloads.py` fetches the **latest** PS5 release of zftpd and
MemDBG from the GitHub API and stores them under `payloads/` with stable
names, then writes `payloads/manifest.json` (tag, asset, size, sha256).

```sh
python3 tools/update_payloads.py          # update anything that changed
python3 tools/update_payloads.py --force  # re-download everything
python3 tools/update_payloads.py --check  # report versions, write nothing
```

A GitHub Actions workflow (`.github/workflows/update-payloads.yml`) runs the
updater daily and on `workflow_dispatch`, committing any new payloads
automatically.

The web UI (`index.html` and the in-console payload menu) reads
`payloads/manifest.json` to display the bundled versions, and does a
best-effort check against the GitHub API to hint when a newer release exists.
Note: GitHub's asset CDN does not send CORS headers, so payloads are always
served from the local `payloads/` directory — run the updater on the host to
refresh them.
