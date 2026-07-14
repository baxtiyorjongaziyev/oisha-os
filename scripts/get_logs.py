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
    token = "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"
    job_id = "87192746112"
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
