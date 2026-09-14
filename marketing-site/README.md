# BXK Trader Pro Marketing Site

Static marketing site for `bxktraderpro.com`.

## Local preview

From this folder:

```powershell
& ..\.venv\Scripts\python.exe -m http.server 8081
```

Then open `http://127.0.0.1:8081`.

## Railway

Deploy this folder as a separate Railway service from the same GitHub repository by setting the service root directory to `/marketing-site`.

Recommended domains:
- `bxktraderpro.com` → this marketing service
- `www.bxktraderpro.com` → this marketing service or redirect to apex
- `app.bxktraderpro.com` → existing BXK Trader Pro application
- `bxktraderpro.net` → redirect to `https://bxktraderpro.com`
- `bxkcapitaltrading.com` → separate corporate page later

## Important

The Privacy Policy and Terms of Service included here are launch drafts, not legal advice. Have final commercial terms reviewed before accepting paid subscribers.
