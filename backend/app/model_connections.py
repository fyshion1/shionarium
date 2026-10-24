"""One default model connection for chat, media, memory and plugins.

Saved dashboard settings are authoritative as a whole. Environment variables
bootstrap an unconfigured installation; they never refill deliberately blank
fields in a saved dashboard profile. No secrets are logged or written here.
"""
from . import db
from . import config as env_config


def default_connection(settings=None):
    saved = db.get_brain_default()
    if saved:
        return dict(saved)
    settings = settings or env_config.get_settings()
    return {
        'name': '默认模型连接',
        'base_url': settings.model_base_url,
        'api_key': settings.model_api_key,
        'model': settings.model_chat,
        'vision_base_url': settings.vision_base_url,
        'vision_api_key': settings.vision_api_key,
        'vision_model': settings.model_vision,
    }


def connection_source():
    return 'database' if db.get_brain_default() else 'environment'


def model_settings(settings=None):
    settings = settings or env_config.get_settings()
    config = default_connection(settings)
    url = config.get('base_url', '')
    key = config.get('api_key', '')
    vision_url = config.get('vision_base_url', '') or url
    # Never send the chat credential to a different vision endpoint implicitly.
    vision_key = config.get('vision_api_key', '')
    if not vision_key and vision_url.rstrip('/') == url.rstrip('/'):
        vision_key = key
    return settings.model_copy(update={
        'model_base_url': url, 'model_api_key': key,
        'model_chat': config.get('model', ''),
        'model_vision': config.get('vision_model', ''),
        'vision_base_url': vision_url, 'vision_api_key': vision_key,
    })
