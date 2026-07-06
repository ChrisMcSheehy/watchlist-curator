"""One-time: exchange client_secret.json for a refresh token.

1. In Google Cloud console: create project, enable 'YouTube Data API v3',
   create OAuth client (Desktop app), download as client_secret.json here.
2. Run: python scripts/setup_auth.py
3. Complete the browser consent; copy the printed refresh token into
   GitHub secrets as GOOGLE_REFRESH_TOKEN (plus GOOGLE_CLIENT_ID/SECRET
   from the client_secret.json).
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
print("\nGOOGLE_REFRESH_TOKEN:", creds.refresh_token)
