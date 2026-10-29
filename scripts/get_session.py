switch_tab("27C7253C87FD42DFAABD934CBB0B80D1")
import json

res = js("""(() => {
    return {
        token: localStorage.getItem('awp_token'),
        company: localStorage.getItem('awp_company') || 'company_default',
        service: localStorage.getItem('awp_service') || 'JON_BRENDING'
    };
})()""")

with open('data/utc_session.json', 'w', encoding='utf-8') as f:
    json.dump(res, f)
print('SESSION_SAVED')
