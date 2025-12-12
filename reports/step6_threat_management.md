# Step 6: Threat Management (IDS/IPS) – Risk Assessment

**Date**: 2025-12-12  
**Status**: BLOCKED - Manual Changes Required (MCP Read-Only)

---

## 1. Scope

This step enables threat management features:
- Enable IDS/IPS in detect-only mode first
- Review detected threats
- Gradually enable blocking mode

---

## 2. Current State (from MCP tools)

### 2.1 Threat Management Settings

| Setting | Status |
|---------|--------|
| IDS/IPS Enabled | ❌ Disabled |
| IDS/IPS Mode | IPS (if enabled) |
| DNS Filtering | ✅ Enabled |
| DPI (Deep Packet Inspection) | ✅ Enabled |
| DPI Restrictions | ❌ Disabled |
| Honeypot | ❌ Disabled |

### 2.2 Security Finding

| Finding | Severity | Issue |
|---------|----------|-------|
| F013 | HIGH | IDS/IPS is disabled |

---

## 3. Proposed Changes

### 3.1 Phase 1: Enable Detect-Only Mode

| Setting | Current | Target |
|---------|---------|--------|
| IDS/IPS | Disabled | Enabled |
| Mode | N/A | IDS (detect only) |

### 3.2 Phase 2: Review and Enable Blocking

After reviewing detected threats:
- Analyze false positives
- Adjust sensitivity if needed
- Switch to IPS mode (block mode)

---

## 4. API Access Issue

**CRITICAL**: MCP server has **READ-ONLY** access to UniFi controller.

Changes must be applied manually.

---

## 5. Manual Configuration Instructions

### 5.1 Enable IDS (Detect Mode)

1. UniFi Controller → Settings → Security
2. Find "Intrusion Detection" section
3. Enable "Intrusion Detection System"
4. Set Mode to "Detection Only" (IDS)
5. Select threat categories:
   - ✅ Emerging Threats
   - ✅ Malware
   - ✅ Exploits
   - ✅ P2P
6. Click "Apply"

### 5.2 Review Detections (After 24-48 Hours)

1. UniFi Controller → Traffic & Security → Threats
2. Review detected threats
3. Check for false positives
4. Whitelist legitimate traffic if needed

### 5.3 Enable IPS (Block Mode)

After confirming no false positives:
1. UniFi Controller → Settings → Security
2. Set Mode to "Detection and Prevention" (IPS)
3. Click "Apply"

---

## 6. Rollback Plan

### 6.1 If IPS Blocks Legitimate Traffic

1. UniFi Controller → Settings → Security
2. Switch from IPS to IDS mode (detection only)
3. Review blocked traffic
4. Add exceptions if needed
5. Re-enable IPS

### 6.2 Emergency: Disable IDS/IPS

If causing major issues:
1. UniFi Controller → Settings → Security
2. Disable IDS/IPS entirely
3. Investigate logs
4. Re-enable after fixing configuration

---

## 7. Summary

### 7.1 Changes Applied via MCP

| Change | Status |
|--------|--------|
| Enable IDS | ❌ BLOCKED |
| Configure mode | ❌ BLOCKED |

### 7.2 Manual Actions Required

- [ ] Enable IDS/IPS in detection mode
- [ ] Monitor for 24-48 hours
- [ ] Review detected threats
- [ ] Switch to IPS mode after validation

---

**Step 6 Status**: ⚠️ BLOCKED - Manual intervention required

