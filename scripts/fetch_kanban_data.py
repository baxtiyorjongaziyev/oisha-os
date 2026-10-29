switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(async () => {
    const token = localStorage.getItem('awp_token');
    const company = localStorage.getItem('awp_company');
    const service = localStorage.getItem('awp_service');

    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (company) headers['x-company-id'] = company;

    async function req(path, query = {}) {
        let url = '/api' + path;
        const q = new URLSearchParams(query);
        if (service && service !== '__ALL__') {
            if (!q.has('service')) q.set('service', service);
        }
        const qs = q.toString();
        if (qs) url += '?' + qs;

        try {
            const resp = await fetch(url, { headers });
            const text = await resp.text();
            let data = null;
            try { data = JSON.parse(text); } catch(e) { data = text; }
            return {
                status: resp.status,
                ok: resp.ok,
                data: data
            };
        } catch(err) {
            return { error: err.message };
        }
    }

    const leadsRes = await req('/leads');
    const callsRes = await req('/calls');
    const servicesRes = await req('/services');
    
    return {
        company: company,
        service: service,
        leadsStatus: leadsRes.status,
        leadsCount: Array.isArray(leadsRes.data) ? leadsRes.data.length : (leadsRes.data?.leads?.length || (leadsRes.data ? Object.keys(leadsRes.data) : null)),
        leadsSample: Array.isArray(leadsRes.data) ? leadsRes.data.slice(0, 2) : (leadsRes.data?.leads ? leadsRes.data.leads.slice(0, 2) : leadsRes.data),
        callsStatus: callsRes.status,
        callsCount: Array.isArray(callsRes.data) ? callsRes.data.length : (callsRes.data?.calls?.length || (callsRes.data ? Object.keys(callsRes.data) : null)),
        callsSample: Array.isArray(callsRes.data) ? callsRes.data.slice(0, 2) : (callsRes.data?.calls ? callsRes.data.calls.slice(0, 2) : callsRes.data)
    };
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
