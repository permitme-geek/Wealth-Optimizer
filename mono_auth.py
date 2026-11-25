import httpx
import os
import sys
from dotenv import load_dotenv, set_key

def main():
    # Load environment variables from .env
    env_path = ".env"
    load_dotenv(env_path)
    
    secret_key = os.getenv("MONO_SECRET_KEY")
    if not secret_key:
        print("Error: MONO_SECRET_KEY not found in .env")
        print("Please add your Mono secret key to .env first.")
        sys.exit(1)

    print("--- Mono Authentication Tool ---")
    print("This script exchanges a Mono Connect 'code' for a permanent 'account_id'.")
    print("1. Open your Mono Connect widget in a browser.")
    print("2. Link your account.")
    print("3. Copy the 'code' (it's short-lived).")
    print("--------------------------------")
    
    # Check for command line argument
    if len(sys.argv) > 1:
        code = sys.argv[1].strip()
        print(f"Using code from command line: {code}")
    else:
        code = input("Enter your Mono Connect code: ").strip()
    
    if not code:
        print("Error: No code provided.")
        sys.exit(1)

    url = "https://api.withmono.com/v2/accounts/auth"
    headers = {
        "mono-sec-key": secret_key,
        "Content-Type": "application/json",
        "accept": "application/json"
    }
    payload = {"code": code}

    print("\nExchanging code for account ID...")
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # The account_id is usually in data['data']['id'] or data['id']
            # Based on common Mono API patterns and SETUP.md
            account_id = data.get("id") or data.get("data", {}).get("id") or data.get("account_id")
            
            if not account_id:
                print("Error: Success response received, but no account ID found.")
                print("Response data:", data)
                sys.exit(1)

            print(f"Success! Found Account ID: {account_id}")
            
            # Save to .env
            set_key(env_path, "MONO_ACCOUNT_ID", account_id)
            print(f"Updated {env_path} with MONO_ACCOUNT_ID={account_id}")
            print("\nYou can now run 'python cli.py sync' to pull your live data.")

    except httpx.HTTPStatusError as e:
        print(f"\nAPI Error: {e.response.status_code}")
        print(f"Message: {e.response.text}")
    except Exception as e:
        print(f"\nUnexpected Error: {e}")

if __name__ == "__main__":
    main()
