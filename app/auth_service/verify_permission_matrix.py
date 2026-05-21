import httpx
import asyncio
import sys

BASE_URL = "http://localhost/api/v1"
PASSWORD = "LMS_Test_2024!"

# Expected configurations for all 21 users
USER_EXPECTATIONS = [
    # Global Admin (0 tenant memberships, but is_sysadmin=True)
    {"email": "admin@cpvmtraining.com", "is_sysadmin": True, "tenants": 0, "roles": {}},
    
    # Single-Org: CellularPoint
    {"email": "cp-manager@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-cp": ["is_business_manager"]}},
    {"email": "cp-creator@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-cp": ["is_training_creator"]}},
    {"email": "cp-employee@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-cp": ["is_employee"]}},
    {"email": "cp-dual@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-cp": ["is_business_manager", "is_training_creator"]}},
    
    # Single-Org: ValueMobile
    {"email": "vm-manager@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-vm": ["is_business_manager"]}},
    {"email": "vm-creator@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-vm": ["is_training_creator"]}},
    {"email": "vm-employee@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-vm": ["is_employee"]}},
    {"email": "vm-dual@lms.com", "is_sysadmin": False, "tenants": 1, "roles": {"tenant-vm": ["is_business_manager", "is_training_creator"]}},
    
    # Multi-Org permutations
    {"email": "cross-m-m@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_business_manager"], "tenant-vm": ["is_business_manager"]}},
    {"email": "cross-m-c@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_business_manager"], "tenant-vm": ["is_training_creator"]}},
    {"email": "cross-m-e@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_business_manager"], "tenant-vm": ["is_employee"]}},
    
    {"email": "cross-c-m@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_training_creator"], "tenant-vm": ["is_business_manager"]}},
    {"email": "cross-c-c@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_training_creator"], "tenant-vm": ["is_training_creator"]}},
    {"email": "cross-c-e@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_training_creator"], "tenant-vm": ["is_employee"]}},
    
    {"email": "cross-e-m@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_employee"], "tenant-vm": ["is_business_manager"]}},
    {"email": "cross-e-c@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_employee"], "tenant-vm": ["is_training_creator"]}},
    {"email": "cross-e-e@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_employee"], "tenant-vm": ["is_employee"]}},
    
    {"email": "dual-cp-e-vm@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_business_manager", "is_training_creator"], "tenant-vm": ["is_employee"]}},
    {"email": "dual-both@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_business_manager", "is_training_creator"], "tenant-vm": ["is_business_manager", "is_training_creator"]}},
    {"email": "e-cp-dual-vm@lms.com", "is_sysadmin": False, "tenants": 2, "roles": {"tenant-cp": ["is_employee"], "tenant-vm": ["is_business_manager", "is_training_creator"]}},
]

async def verify_user(client: httpx.AsyncClient, expectation: dict):
    email = expectation["email"]
    try:
        # Step 1: Login to get Session Token
        login_data = {"username": email, "password": PASSWORD}
        resp = await client.post("/auth/login", data=login_data)
        if resp.status_code != 200:
            print(f"[FAIL] {email}: Login failed with {resp.status_code}")
            return False
        
        session_token = resp.json()["session_token"]
        client.headers.update({"Authorization": f"Bearer {session_token}"})
        
        # Step 2: Get Me (verify is_sysadmin)
        me_resp = await client.get("/users/me")
        if me_resp.status_code != 200:
             print(f"[FAIL] {email}: /users/me (session) failed with {me_resp.status_code}")
             return False
        
        user_data = me_resp.json()
        if user_data.get("is_sysadmin") != expectation["is_sysadmin"]:
            print(f"[FAIL] {email}: Expected is_sysadmin={expectation['is_sysadmin']}, got {user_data.get('is_sysadmin')}")
            return False
        
        if expectation["is_sysadmin"] and expectation["tenants"] == 0:
            print(f"[PASS] {email} (Global Admin)")
            return True

        # Step 3: Get Tenants
        tenants_resp = await client.get("/auth/tenants")
        if tenants_resp.status_code != 200:
            print(f"[FAIL] {email}: /auth/tenants failed with {tenants_resp.status_code}")
            return False
        
        tenants = tenants_resp.json()
        if len(tenants) < expectation["tenants"]:
             print(f"[FAIL] {email}: Expected {expectation['tenants']} tenants, got {len(tenants)}")
             return False
        
        # Step 4: Verify each tenant select and roles
        for tenant_id, expected_roles in expectation["roles"].items():
            # Select Tenant
            sel_resp = await client.post("/auth/select-tenant", json={"tenant_id": tenant_id})
            if sel_resp.status_code != 200:
                print(f"[FAIL] {email}: Failed to select tenant {tenant_id}")
                return False
            
            access_token = sel_resp.json()["access_token"]
            
            # Use access_token to verify roles via /users/me
            # (or we can just check the token claims if we had a decoder, 
            # but /users/me is better as it tests the actual implementation)
            temp_headers = {"Authorization": f"Bearer {access_token}"}
            role_verify_resp = await client.get("/users/me", headers=temp_headers)
            if role_verify_resp.status_code != 200:
                print(f"[FAIL] {email}: /users/me (access) failed for {tenant_id}")
                return False
            
            final_user_data = role_verify_resp.json()
            # Note: The 'members' list in /users/me contains all memberships.
            # We need to check the one matching tenant_id.
            m = next((m for m in final_user_data.get("members", []) if m["tenant_id"] == tenant_id), None)
            if not m:
                print(f"[FAIL] {email}: Missing membership data for {tenant_id}")
                return False
            
            for role_field in expected_roles:
                if not m.get(role_field):
                    print(f"[FAIL] {email}: Missing role {role_field} in {tenant_id}")
                    return False
        
        print(f"[PASS] {email}")
        return True

    except Exception as e:
        print(f"[ERROR] {email}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        results = []
        for exp in USER_EXPECTATIONS:
            success = await verify_user(client, exp)
            results.append(success)
            # Clear headers for next user
            if "Authorization" in client.headers:
                del client.headers["Authorization"]
        
        total = len(results)
        passed = sum(1 for r in results if r)
        print(f"\nSummary: {passed}/{total} Passed")
        if passed != total:
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
