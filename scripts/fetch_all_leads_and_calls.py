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

    // 1. Fetch all leads (take=500)
    const leadsResp = await fetch('/api/leads?take=500', { headers });
    const leadsJson = await leadsResp.json();
    const leads = (leadsJson.data && leadsJson.data.leads) ? leadsJson.data.leads : [];

    // 2. Sample 30 leads across different statuses (Sell, V_PROTSESSE, Perezvon, Not interested)
    const candidates = [];
    // Prioritize Sell and V_PROTSESSE and Perezvon first
    const prioritized = leads.filter(l => ['Sell', 'V_PROTSESSE', 'Perezvon'].includes(l.status));
    const others = leads.filter(l => !['Sell', 'V_PROTSESSE', 'Perezvon'].includes(l.status));
    const toCheck = [...prioritized, ...others.slice(0, 30)];

    const leadsWithCalls = [];
    let checkedCount = 0;

    for (const lead of toCheck) {
        checkedCount++;
        try {
            const evResp = await fetch(`/api/leads/${lead.id}/events`, { headers });
            const evJson = await evResp.json();
            const events = (evJson.data && evJson.data.events) ? evJson.data.events : [];
            const calls = events.filter(e => e.type === 'call' || e.call || e.recordingId);
            
            if (calls.length > 0 || events.length > 0) {
                leadsWithCalls.push({
                    id: lead.id,
                    cardNo: lead.cardNo,
                    name: lead.name,
                    phone: lead.phoneNumber,
                    status: lead.status,
                    board: lead.board,
                    operator: lead.assignedToOperator,
                    totalEvents: events.length,
                    callsCount: calls.length,
                    calls: calls.map(c => ({
                        id: c.id,
                        type: c.type,
                        recordingId: c.recordingId || (c.call ? c.call.recordingId : null),
                        createdAt: c.createdAt,
                        callData: c.call || null,
                        comment: c.comment || null
                    }))
                });
            }
        } catch(e) {}
    }

    // 3. Test recording download for the first call that has recordingId
    let testAudio = null;
    const callWithRec = leadsWithCalls.flatMap(l => l.calls).find(c => c.recordingId);
    if (callWithRec) {
        try {
            const aResp = await fetch(`/api/recordings/${callWithRec.recordingId}/file`, { headers });
            testAudio = {
                recordingId: callWithRec.recordingId,
                status: aResp.status,
                contentType: aResp.headers.get('content-type'),
                contentLength: aResp.headers.get('content-length'),
                ok: aResp.ok
            };
        } catch(e) {
            testAudio = { error: e.message };
        }
    }

    return {
        totalLeadsInSystem: leads.length,
        checkedCount,
        leadsWithCallsCount: leadsWithCalls.length,
        sampleLeadsWithCalls: leadsWithCalls.slice(0, 10),
        testAudio
    };
})()""")

print(json.dumps(res, indent=2, ensure_ascii=False))
