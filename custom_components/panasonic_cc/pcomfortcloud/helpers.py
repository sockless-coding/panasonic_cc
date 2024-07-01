import logging
from aiohttp import ClientResponse
from . import exceptions
from .constants import CHECK_RESPONSE_ERROR_MESSAGE, CHECK_RESPONSE_ERROR_MESSAGE_WITH_PAYLOAD

_LOGGER = logging.getLogger(__name__)

async def has_new_version_been_published(response: ClientResponse) -> bool:
    if response.status != 401:
        return False
    response_text = await response.text()
    return '4106' in response_text

async def check_response(response: ClientResponse, function_description: str, expected_status:int, payload = None):
    
    if response.status != expected_status:
        response_text = await response.text()
 
        if payload is not None:
            _LOGGER.error(
                CHECK_RESPONSE_ERROR_MESSAGE_WITH_PAYLOAD, 
                function_description, 
                expected_status, response.status, 
                payload,
                response_text)
        else:
            _LOGGER.error(
                CHECK_RESPONSE_ERROR_MESSAGE, 
                function_description, 
                expected_status, response.status, 
                response_text)
        raise exceptions.ResponseError(
            f"({function_description}: Expected status code {expected_status}, received: {response.status}: " +
            f"{response_text}"
        )
    
