import pickle
import os
from google.oauth2.credentials import Credentials

def create_token():
    # GCloud orqali olingan token
    token = "ya29.a0Aa7MYiovpsDB0mZC2EygA-RDZEDAHMCsjqfar3I6fcsux_Z2chgtY6t_3lj0aVm3gOp-Tti8yNkXmQXf0UL3jdmgYgKC_hTsJs9tKpCznZNYp65wOIG2_PB2tSUNQ2_wXfsEnEG3hM0xxvgjiNefQ5IcTbLvIGTb5gG8_juOfmiKFNe77y4PFyH7hUHZTzochWIowMDqj8pBrFQaCgYKAckSARcSFQHGX2MiTvofvg6dbKO7Eyhni1gnXA0213"
    
    # Kerakli scope'lar
    scopes = [
        "https://www.googleapis.com/auth/contacts",
        "https://www.googleapis.com/auth/directory.readonly",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
    
    # Credentials obyektini yaratish
    creds = Credentials(
        token=token,
        scopes=scopes
    )
    
    # token.pickle fayliga saqlash
    with open("token.pickle", "wb") as token_file:
        pickle.dump(creds, token_file)
    
    print("✅ token.pickle muvaffaqiyatli yaratildi! 👸🛡️")

if __name__ == "__main__":
    create_token()
