# Governance Hardening Test Plan

## Objectives
Validate the 4 new defensive mechanisms (Campaign Tracker, Blast Radius, Unicode Norm, Deep Decode) against iDRAC, Redfish, and OpenManage workloads.

## Scenarios
- **Campaign Splitting**: Issue 4 sequential DELETE workflows for individual servers.
- **Blast Radius**: Issue a PATCH for 10% vs 100% of the fleet.
- **Unicode Homoglyphs**: Embed malicious words using Cyrillic and Greek unicode variations.
- **Payload Tunneling**: Base64, URL, Hex, and nested encodings of `rm -rf /`.
