
from exchange.bingx_client import BingXClient

client = BingXClient()

response = client.request(
    "GET",
    "/openApi/contract/v1/balance"
)

print(response)