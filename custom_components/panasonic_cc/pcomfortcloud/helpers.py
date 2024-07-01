from aiohttp import ClientResponse

async def has_new_version_been_published(response: ClientResponse) -> bool:
    if response.status != 401:
        return False
    response_text = await response.text()
    return '4106' in response_text

