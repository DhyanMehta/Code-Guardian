<!-- codeguardian-review:88 -->
> **Correction prepared November 6, 2026.** Source revalidation of the original commit reduced 92 observations to 85: two contradicted length claims, three duplicate length entries, and two false module-level advisories were removed. No new provider analysis was used for this historical correction. Ten Quality documentation advisories corroborate Documentation findings; one import-style suggestion remains unverified and informational. Original structured file coverage was not recorded; Quality explicitly excluded eight frontend files.

## CodeGuardian Review — PR #1

**Status**: Completed — all four agents executed. Quality coverage was partial.
**Commit**: `c1c01ff`

### Summary
- 3 high-severity (3 quality)
- 14 medium-severity (10 documentation, 4 test gap)
- 12 low-severity (7 documentation, 2 security, 3 test gap)
- 56 info-severity (11 quality, 45 security)
- Auto-fix available for 5 finding(s)

> **Incomplete coverage**: Quality has incomplete or unrecorded coverage. Saved findings are included below; exclusions and limitations apply.

---

### Findings

#### 🔴 High

| # | Agent | File | Finding |
|---|-------|------|---------|
| 1 | Quality | `backend/app/services/analytics_service.py:85` | maximum_function_length: membership_breakdown contains 42 nonblank logic lines; the cited limit is 40. |
| 2 | Quality | `backend/app/services/analytics_service.py:134` | maximum_function_length: event_attendance contains 49 nonblank logic lines; the cited limit is 40. |
| 3 | Quality | `backend/tests/test_analytics.py:147` | maximum_function_length: test_analytics_counts_correct contains 226 nonblank logic lines; the cited limit is 40. |

#### 🟡 Medium

| # | Agent | File | Finding |
|---|-------|------|---------|
| 4 | Test Gap | `backend/app/services/analytics_service.py:33` | No direct test reference: club_summary: Risk score: 5.0/10 |
| 5 | Test Gap | `backend/app/services/analytics_service.py:85` | No direct test reference: membership_breakdown: Risk score: 5.2/10 |
| 6 | Test Gap | `backend/app/services/analytics_service.py:134` | No direct test reference: event_attendance: Risk score: 5.8/10 |
| 7 | Test Gap | `backend/app/services/analytics_service.py:191` | No direct test reference: revenue_by_type: Risk score: 5.2/10 |
| 8 | Documentation | `backend/app/schemas/analytics.py:10` | Docstring missing: ClubSummaryOut: Function at backend/app/schemas/analytics.py:10 |
| 9 | Documentation | `backend/app/schemas/analytics.py:17` | Docstring missing: MembershipBreakdownOut: Function at backend/app/schemas/analytics.py:17 |
| 10 | Documentation | `backend/app/schemas/analytics.py:23` | Docstring missing: EventAttendanceOut: Function at backend/app/schemas/analytics.py:23 |
| 11 | Documentation | `backend/app/schemas/analytics.py:32` | Docstring missing: RevenueByTypeOut: Function at backend/app/schemas/analytics.py:32 |
| 12 | Documentation | `backend/app/schemas/analytics.py:38` | Docstring missing: RecentActivityOut: Function at backend/app/schemas/analytics.py:38 |
| 13 | Documentation | `backend/tests/test_analytics.py:40` | Docstring missing: test_analytics_requires_auth: Function at backend/tests/test_analytics.py:40 |
| 14 | Documentation | `backend/tests/test_analytics.py:47` | Docstring missing: test_analytics_requires_permission: Function at backend/tests/test_analytics.py:47 |
| 15 | Documentation | `backend/tests/test_analytics.py:58` | Docstring missing: test_analytics_returns_dashboard: Function at backend/tests/test_analytics.py:58 |
| 16 | Documentation | `backend/tests/test_analytics.py:87` | Docstring missing: test_analytics_empty_club: Function at backend/tests/test_analytics.py:87 |
| 17 | Documentation | `backend/tests/test_analytics.py:147` | Docstring missing: test_analytics_counts_correct: Function at backend/tests/test_analytics.py:147 |

#### ⚪ Low

| # | Agent | File | Finding |
|---|-------|------|---------|
| 18 | Security | `backend/tests/test_analytics.py:336` | B106: Hardcoded password appears in test data; not used in production. |
| 19 | Security | `backend/tests/test_analytics.py:347` | B106: Hardcoded password appears in test data; not used in production. |
| 20 | Test Gap | `backend/app/api/v1/endpoints/analytics.py:20` | No direct test reference: get_club_analytics_dashboard: Risk score: 1.0/10 |
| 21 | Test Gap | `backend/app/services/analytics_service.py:234` | No direct test reference: recent_activity: Risk score: 3.4/10 |
| 22 | Test Gap | `backend/app/services/analytics_service.py:265` | No direct test reference: get_dashboard_data: Risk score: 1.7/10 |
| 23 | Documentation | `backend/app/api/v1/endpoints/analytics.py:20` | Docstring incomplete: get_club_analytics_dashboard: Function at backend/app/api/v1/endpoints/analytics.py:20 |
| 24 | Documentation | `backend/app/services/analytics_service.py:33` | Docstring incomplete: club_summary: Function at backend/app/services/analytics_service.py:33 |
| 25 | Documentation | `backend/app/services/analytics_service.py:85` | Docstring incomplete: membership_breakdown: Function at backend/app/services/analytics_service.py:85 |
| 26 | Documentation | `backend/app/services/analytics_service.py:134` | Docstring incomplete: event_attendance: Function at backend/app/services/analytics_service.py:134 |
| 27 | Documentation | `backend/app/services/analytics_service.py:191` | Docstring incomplete: revenue_by_type: Function at backend/app/services/analytics_service.py:191 |
| 28 | Documentation | `backend/app/services/analytics_service.py:234` | Docstring incomplete: recent_activity: Function at backend/app/services/analytics_service.py:234 |
| 29 | Documentation | `backend/app/services/analytics_service.py:265` | Docstring incomplete: get_dashboard_data: Function at backend/app/services/analytics_service.py:265 |

#### ℹ️ Info

| # | Agent | File | Finding |
|---|-------|------|---------|
| 30 | Security | `backend/tests/test_analytics.py:43` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 31 | Security | `backend/tests/test_analytics.py:54` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 32 | Security | `backend/tests/test_analytics.py:65` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 33 | Security | `backend/tests/test_analytics.py:68` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 34 | Security | `backend/tests/test_analytics.py:69` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 35 | Security | `backend/tests/test_analytics.py:70` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 36 | Security | `backend/tests/test_analytics.py:71` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 37 | Security | `backend/tests/test_analytics.py:72` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 38 | Security | `backend/tests/test_analytics.py:75` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 39 | Security | `backend/tests/test_analytics.py:76` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 40 | Security | `backend/tests/test_analytics.py:77` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 41 | Security | `backend/tests/test_analytics.py:78` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 42 | Security | `backend/tests/test_analytics.py:81` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 43 | Security | `backend/tests/test_analytics.py:82` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 44 | Security | `backend/tests/test_analytics.py:83` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 45 | Security | `backend/tests/test_analytics.py:112` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 46 | Security | `backend/tests/test_analytics.py:127` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 47 | Security | `backend/tests/test_analytics.py:130` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 48 | Security | `backend/tests/test_analytics.py:131` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 49 | Security | `backend/tests/test_analytics.py:132` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 50 | Security | `backend/tests/test_analytics.py:133` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 51 | Security | `backend/tests/test_analytics.py:135` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 52 | Security | `backend/tests/test_analytics.py:136` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 53 | Security | `backend/tests/test_analytics.py:137` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 54 | Security | `backend/tests/test_analytics.py:138` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 55 | Security | `backend/tests/test_analytics.py:141` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 56 | Security | `backend/tests/test_analytics.py:142` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 57 | Security | `backend/tests/test_analytics.py:143` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 58 | Security | `backend/tests/test_analytics.py:386` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 59 | Security | `backend/tests/test_analytics.py:391` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 60 | Security | `backend/tests/test_analytics.py:392` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 61 | Security | `backend/tests/test_analytics.py:393` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 62 | Security | `backend/tests/test_analytics.py:396` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 63 | Security | `backend/tests/test_analytics.py:399` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 64 | Security | `backend/tests/test_analytics.py:400` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 65 | Security | `backend/tests/test_analytics.py:401` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 66 | Security | `backend/tests/test_analytics.py:406` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 67 | Security | `backend/tests/test_analytics.py:407` | B101: Assert statements in test code are harmless and removed in optimized runs; not a security risk. |
| 68 | Security | `backend/tests/test_analytics.py:408` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 69 | Security | `backend/tests/test_analytics.py:409` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 70 | Security | `backend/tests/test_analytics.py:413` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 71 | Security | `backend/tests/test_analytics.py:414` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 72 | Security | `backend/tests/test_analytics.py:415` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 73 | Security | `backend/tests/test_analytics.py:419` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 74 | Security | `backend/tests/test_analytics.py:421` | B101: Assert statements in test code are harmless and removed in optimized runs. |
| 75 | Quality | `backend/app/schemas/analytics.py:10` | Advisory: MissingDocstring: Public class &#x27;ClubSummaryOut&#x27; does not have a one-line docstring as required for public classes. |
| 76 | Quality | `backend/app/schemas/analytics.py:17` | Advisory: MissingDocstring: Public class &#x27;MembershipBreakdownOut&#x27; does not have a one-line docstring as required for public classes. |
| 77 | Quality | `backend/app/schemas/analytics.py:23` | Advisory: MissingDocstring: Public class &#x27;EventAttendanceOut&#x27; does not have a one-line docstring as required for public classes. |
| 78 | Quality | `backend/app/schemas/analytics.py:32` | Advisory: MissingDocstring: Public class &#x27;RevenueByTypeOut&#x27; does not have a one-line docstring as required for public classes. |
| 79 | Quality | `backend/app/schemas/analytics.py:38` | Advisory: MissingDocstring: Public class &#x27;RecentActivityOut&#x27; does not have a one-line docstring as required for public classes. |
| 80 | Quality | `backend/tests/test_analytics.py` | Advisory: import_order: Suggestion to review import organization against the team formatter. This policy interpretation remains unverified. |
| 81 | Quality | `backend/tests/test_analytics.py:40` | Advisory: missing_docstring: Public test function lacks a one-line docstring as required by passage 3.4 |
| 82 | Quality | `backend/tests/test_analytics.py:47` | Advisory: missing_docstring: Public test function lacks a one-line docstring as required by passage 3.4 |
| 83 | Quality | `backend/tests/test_analytics.py:58` | Advisory: missing_docstring: Public test function lacks a one-line docstring as required by passage 3.4 |
| 84 | Quality | `backend/tests/test_analytics.py:87` | Advisory: missing_docstring: Public test function lacks a one-line docstring as required by passage 3.4 |
| 85 | Quality | `backend/tests/test_analytics.py:147` | Advisory: missing_docstring: Public test function lacks a one-line docstring as required by passage 3.4 |

---

### Agent Status

| Agent | Status | Findings |
|-------|--------|----------|
| Documentation | ✅ — Coverage not recorded | 17 |
| Security | ✅ — Coverage not recorded | 47 |
| Quality | ⚠️ completed with limitations (Quality coverage excludes non-Python and generated/vendor files.) — Coverage not recorded | 14 |
| Test Gap | ✅ — Coverage not recorded | 7 |

---

### Auto-Fix Available

5 finding(s) have auto-generated fixes (test drafts, docstrings). No code is pushed without your explicit approval.

---
*Generated by CodeGuardian AI*