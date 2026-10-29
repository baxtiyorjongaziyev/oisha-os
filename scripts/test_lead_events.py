switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(async () => {
    const token = localStorage.getItem('awp_token');
    const company = localStorage.getItem('awp_company') || 'company_default';
    const service = localStorage.getItem('awp_service') || 'JON_BRENDING';

    const headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    if (company) headers['x-company-id'] = company;

    // 1. Get leads from /api/leads
    const leadsResp = await fetch('/api/leads?take=20', { headers });
    const leadsJson = await leadsResp.json();
    const leads = (leadsJson.data && leadsJson.data.leads) ? leadsJson.data.leads : (leadsJson.leads || []);

    // 2. For each lead, fetch /api/leads/${id}/events
    const sampleResults = [];
    let totalCallsFound = 0;
    let recordingIdsFound = [];

    for (const lead of leads.slice(0, 15)) {
        try {
            const evResp = await fetch(`/api/leads/${lead.id}/events`, { headers });
            const evJson = await evResp.json();
            const events = evJson.data || evJson;
            const calls = Array.isArray(events) ? events.filter(e => e.type === 'call' || e.call || e.recordingId) : [];
            totalCallsFound += calls.length;
            calls.forEach(c => {
                if (c.recordingId) recordingIdsFound.push(c.recordingId);
                if (c.call && c.call.recordingId) recordingIdsFound.push(c.call.recordingId);
            });
            sampleResults.push({
                leadId: lead.id,
                cardNo: lead.cardNo,
                name: lead.name,
                phone: lead.phoneNumber,
                status: lead.status,
                eventsCount: Array.isArray(events) ? events.length : 0,
                callsCount: calls.length,
                calls: calls
            });
        } catch(e) {
            sampleResults.push({ leadId: lead.id, error: e.message });
        }
    }

    // 3. Test fetching the first recording file if any found
    let recordingTest = null;
    if (recordingIdsFound.length > 0) {
        const recId = recordingIdsFound[0];
        try {
            const rResp = await fetch(`/api/recordings/${recId}/file`, { headers });
            recordingTest = {
                recordingId: recId,
                status: rResp.status,
                contentType: rResp.headers.get('content-type'),
                contentLength: rResp.headers.get('content-length'),
                ok: rResp.ok
            };
        } catch(e) {
            recordingTest = { recordingId: recId, error: e.message };
        }
    }

    return {
        leadsFetched: leads.length,
        sampleResults,
        totalCallsFound,
        recordingIdsFound,
        recordingTest
    };
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
