switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(async () => {
    const token = localStorage.getItem('awp_token');
    const headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const testEndpoints = [
        '/auth/me',
        '/leads',
        '/calls',
        '/recordings/list',
        '/api/recordings/list'
    ];

    const results = {};
    for (const ep of testEndpoints) {
        try {
            const resp = await fetch(ep, { headers });
            results[ep] = {
                status: resp.status,
                ok: resp.ok,
                statusText: resp.statusText,
                contentType: resp.headers.get('content-type')
            };
            if (resp.ok) {
                const text = await resp.text();
                try {
                    const parsed = JSON.parse(text);
                    if (Array.isArray(parsed)) {
                        results[ep].type = 'array';
                        results[ep].count = parsed.length;
                        results[ep].sample = parsed[0];
                    } else if (typeof parsed === 'object' && parsed !== null) {
                        results[ep].type = 'object';
                        results[ep].keys = Object.keys(parsed);
                        results[ep].sample = parsed;
                    }
                } catch(e) {
                    results[ep].textSnippet = text.substring(0, 100);
                }
            }
        } catch(err) {
            results[ep] = { error: err.message };
        }
    }
    return results;
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
