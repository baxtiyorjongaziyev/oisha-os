import asyncio
from settings import settings
from amocrm_sync import AmoCRMSync

async def initialize_token():
    auth_code = "def50200e4e609d8094ea3ab7154eb6bc25aa5a775017d7794562b658b32363806de431f6ce0e15f8bfe3814958e2685f37454ec40ecf935ecceec2e34402fa00e15a85112e1b3492fae99f82f2cb65cf1832e066791dc0039b000c0a0dd4986e4e59e1c8aaf28d47aabfbbb7572c7dad6f22f297490f95d371c02f669585700cdaa9728b9cfad6b91ab083ad2aa6246f4a29b31416d4696c3d4022483417c1cce21f8854ed07c5080c9df7b3985888d61e41edad7b9fa15d07fa48576a5d26e8f56938fcd50c9fc7d57c306b5395f32c67cefede2128fb76fa5666df277bd9a1dfc1604100e2ec6229b08aa4310158e0c732a1502c7ffccd74fc703c24854c232e55062dd0a17101b0010d4d354c29f79580214c78f85b09f166cfd478d5c2ba62a9d6a2c3454c57cc4252f39452112ba73b75d7ee97f01d59b726d715b0d4fc988b1950f88dd8228a85b2a7068db0de3bf20fdd4239ddac060192429f00a38c5d53ad79bf029f96af4934c22e289a5658fdbd4043636589ac1dfba48df1dd8ce7e3ce6b35f1bc6a6fc445d2ea99dfb19d68064e95b73ff382045b8c7ee2c0769c54049ea9f84c297fb02b48aab0312a516c29df04c6282751ffe9656499e4fc7c22a57e2ffa2219a00747c32ddaf3e365a79093b1a91199572ac6975966b5034d8379aa5fee732c0496951f0e4e67d0d4519950199d8f05f30a129393721f4e68f82c002b50f7b560a9f4894b266812ebd1910a5a1d9310df3c6aa0eaebc6e6046aae4e03106"
    
    amo = AmoCRMSync(
        subdomain=settings.AMOCRM_SUBDOMAIN,
        client_id=settings.AMOCRM_CLIENT_ID,
        client_secret=settings.AMOCRM_CLIENT_SECRET.get_secret_value() if settings.AMOCRM_CLIENT_SECRET else None,
        redirect_url=settings.AMOCRM_REDIRECT_URL
    )
    
    print("Initial authorization starting...")
    success = amo.authorize_initial(auth_code)
    if success:
        print("✅ Tokens initialized and saved to amocrm_token.json")
    else:
        print("❌ Authorization failed.")

if __name__ == "__main__":
    asyncio.run(initialize_token())
