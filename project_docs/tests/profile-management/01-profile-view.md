# Profile View Test Cases

Covers role-based visibility on the profile page (`/profile/:username`).

---

## Access Control

| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PRF-01 | User can view their own profile | Any logged-in user | Navigate to `/profile/{own_username}` | Profile page loads | happy |
| TC-PRF-02 | Business Manager can view employee profile in same tenant | Manager + employee in same tenant | Navigate to employee's profile URL | Profile page loads | happy |
| TC-PRF-03 | Training Creator can view collaborator profile in same tenant | Creator + collaborator in same tenant | Navigate to collaborator's profile URL | Profile page loads | happy |
| TC-PRF-04 | Base Employee cannot view another user's profile | Employee | Navigate to colleague's profile URL | 403 — access denied page shown | auth |
| TC-PRF-05 | Manager cannot view profile of user in another tenant | Manager of Tenant A + Tenant B user | Navigate to Tenant B user's profile | 403 — profile not in same tenant | isolation |
| TC-PRF-06 | SysAdmin can view any user's profile | SysAdmin | Navigate to any user's profile | Profile page loads with full data | happy |
| TC-PRF-07 | Old profile URL returns 404 after username change | User changes username | Access old `/profile/{old_username}` | 404 | edge |
| TC-PRF-08 | Profile with unknown username returns 404 | Any user | Navigate to `/profile/doesnotexist` | 404 | edge |

---

## Content Visibility by Viewer Role

### Own Profile
| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PRF-09 | Own profile shows personal details (name, avatar, email, username) | User views own profile | Open profile | All personal fields visible | happy |
| TC-PRF-10 | Own profile shows completed certificates | User has certificates | Open own profile | Certificates tab/section visible with all earned certs | happy |
| TC-PRF-11 | Own profile shows settings link | Any user | Open own profile | Settings shortcut visible | happy |

### Employee Viewing Another Employee
| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PRF-12 | Employee sees only basic info on another's profile | Employee views colleague | Open profile (if access allowed) | Name, avatar, department only — no training data | auth |

### Manager Viewing Employee Profile
| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PRF-13 | Manager sees training assignment and progress on employee profile | Manager + employee with enrolled training | View employee profile | Assignments, progress percentages visible | happy |
| TC-PRF-14 | Manager sees completed certificates on employee profile | Employee has certificate | View employee profile | Certificate(s) listed with download option | happy |
| TC-PRF-15 | Manager sees group memberships on employee profile | Employee in 2 groups | View profile | Groups listed | happy |
| TC-PRF-16 | Manager sees activity log on employee profile | Employee has activity | View profile | Activity log visible | happy |

### SysAdmin Viewing Any Profile
| ID | Scenario | Pre-condition | Steps | Expected | Type |
|---|---|---|---|---|---|
| TC-PRF-17 | SysAdmin sees all tenant memberships on profile | User in 3 tenants | SysAdmin views profile | All 3 tenant memberships shown | happy |
| TC-PRF-18 | SysAdmin sees full activity log across all tenants | User has activity in multiple tenants | SysAdmin views profile | Cross-tenant activity visible | happy |
| TC-PRF-19 | SysAdmin sees "Edit Name" option on any profile | SysAdmin on any profile | View profile | Edit name button/option visible | happy |
| TC-PRF-20 | Non-SysAdmin does not see "Edit Name" option | Manager on employee profile | View profile | No edit name button | auth |
