# Oisha-OS Final Integration Tasks

- [/] Phase 6b: Stability Fixes (GCP 3.11)
  - [x] Fix `src/main.py` syntax
  - [ ] Fix `src/services/proactive_worker.py` syntax
  - [ ] Sweep other files for f-string backslashes
- [ ] Phase 9: AmoCRM Real-time Note Sync
  - [ ] Add `add_note_to_contact` in `src/services/amocrm_sync.py`
  - [ ] Inject note-sync logic into `MessageController` and `main.py` handler
- [ ] Phase 10: Manus AI MCP Bridge
  - [ ] Implement `src/mcp_server.py`
  - [ ] Expose Oisha tools via MCP manifest
  - [ ] Test local connectivity
- [ ] Phase 11: Deployment & Verification
  - [ ] Update `.env` with MCP settings
  - [ ] Restart `oisha.service`
  - [ ] Final end-to-end check
