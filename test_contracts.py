from exchange.bingx_client import BingXClient

client = BingXClient()

print(client.get_contract_info())
