import os
import urllib.request
import json
import sys

class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if 'api.github.com' not in newurl:
            new_req.remove_header('Authorization')
        return new_req

def main():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)
    job_id = os.environ.get("JOB_ID") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not job_id:
        print("Error: pass JOB_ID via env var or as the first argument.")
        sys.exit(1)
    url = f"https://api.github.com/repos/baxtiyorjongaziyev/oisha-os/actions/jobs/{job_id}/logs"
    
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'python',
            'Authorization': f'token {token}'
        }
    )
    
    opener = urllib.request.build_opener(NoAuthRedirect)
    try:
        response = opener.open(req)
        logs = response.read().decode('utf-8')
        print("--- MATCHED LOG LINES ---")
        for line in logs.splitlines():
            if any(w in line.lower() for w in ['nginx', 'reload', 'readyz', 'healthz', 'copy', 'sync', 'sites-available']):
                print(line)
    except Exception as e:
        print(f"Error fetching logs: {e}")

if __name__ == "__main__":
    main()
