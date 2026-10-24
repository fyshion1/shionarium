"""Unified defaults use isolated SQLite and synthetic, never contacted URLs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db, model_connections as connections
from app.config import Settings
from app.routers import chat, nest, images, gallery, model_config
from app.services import memory


class ModelConnectionsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for name, value in [('DB_PATH', Path(temporary.name) / 'test.sqlite'),
                            ('DATA_DIR', Path(temporary.name))]:
            context = patch.object(db, name, value)
            context.start(); self.addCleanup(context.stop)
        with db._tx() as connection:
            connection.executescript(db._SCHEMA)
            db._migrate(connection)
        self.environment = Settings(_env_file=None, model_base_url='https://env.invalid/v1',
                                    model_api_key='env-test-key', model_chat='env-chat',
                                    model_vision='env-vision', vision_base_url='', vision_api_key='')
        context = patch('app.config.get_settings', return_value=self.environment)
        context.start(); self.addCleanup(context.stop)
        app = FastAPI()
        for router in [nest.router, chat.router, images.router, gallery.router, model_config.router]:
            app.include_router(router, prefix='/api')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def save(self, **changes):
        body = {'base_url':'https://saved.invalid/v1', 'api_key':'saved-test-key',
                'model':'saved-chat', 'vision_model':'saved-vision', **changes}
        response = self.client.put('/api/nest/api-config', json=body)
        self.assertEqual(response.status_code, 200)

    def test_env_bootstraps_chat_dashboard_plugins_and_memory_without_writing_db(self):
        self.assertEqual(self.client.get('/api/nest/api-config').json()['config']['model'], 'env-chat')
        self.assertEqual(chat._brain_route()['model'], 'env-chat')
        self.assertEqual(nest._effective_config('core')['model'], 'env-chat')
        self.assertEqual(memory.embeddings_config()['base_url'], 'https://env.invalid/v1')
        self.assertEqual(db.get_brain_default(), {})

    def test_one_dashboard_save_updates_all_defaults_without_restart(self):
        self.save()
        from app.tavern_feature import TavernSDK
        self.assertEqual(TavernSDK('synthetic_test_host').get_settings().model_chat, 'saved-chat')
        self.assertEqual(chat._brain_route()['base_url'], 'https://saved.invalid/v1')
        self.assertEqual(nest._effective_config('core')['model'], 'saved-chat')
        self.assertEqual(memory.embeddings_config()['api_key'], 'saved-test-key')
        self.assertEqual(self.client.get('/api/model-config').json()['source'], 'database')
        self.save(model='new-chat')
        self.assertEqual(chat._brain_route()['model'], 'new-chat')

    def test_saved_blanks_never_refill_old_env_key_or_vision(self):
        self.save(api_key='', vision_model='')
        self.assertEqual(chat._brain_route()['api_key'], '')
        self.assertEqual(chat._brain_route(vision=True)['model'], '')
        self.assertEqual(self.client.post('/api/images/chat', json={'image_base64':'fixture'}).status_code, 409)

    def test_separate_vision_endpoint_never_inherits_chat_credential(self):
        self.save(vision_base_url='https://vision.invalid/v1', vision_api_key='')
        self.assertEqual(chat._brain_route(vision=True)['api_key'], '')
        self.assertEqual(nest._effective_config('core')['vision_api_key'], '')
        self.save(vision_base_url='https://vision.invalid/v1', vision_api_key='vision-test-key')
        self.assertEqual(chat._brain_route(vision=True)['api_key'], 'vision-test-key')

    def test_gallery_uses_dashboard_vision_connection_and_not_env(self):
        self.save(vision_base_url='https://vision.invalid/v1', vision_api_key='vision-test-key')
        with patch.object(gallery.db, 'get_gallery', return_value={'orig':'fixture', 'thumb':'', 'kind':'image'}), \
             patch.object(gallery.gal, 'describe_image', new_callable=AsyncMock, return_value='test description') as describe:
            response = self.client.post('/api/gallery/test/describe', json={'save':False})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(describe.call_args.kwargs['base_url'], 'https://vision.invalid/v1')
        self.assertEqual(describe.call_args.kwargs['api_key'], 'vision-test-key')

    def test_chat_http_stream_uses_env_then_saved_connection_without_restart(self):
        routes = []
        async def stream(messages, model, base_url, api_key, **kwargs):
            routes.append((model, base_url, api_key))
            yield {'type':'text', 'text':'synthetic reply'}
            yield {'type':'done'}
        with patch.object(chat, '_to_openai_messages', return_value=[{'role':'user','content':'test'}]), \
             patch.object(chat, '_resolve_persona', return_value={}), \
             patch('app.services.conversation_runtime.transient_stream', stream):
            body = {'messages':[{'role':'user','content':'test'}],
                    'model':'retired-browser-model', 'base_url':'https://retired.invalid/v1', 'api_key':'retired-key'}
            response = self.client.post('/api/chat', json=body)
            self.assertEqual(response.status_code, 200)
            self.assertIn('synthetic reply', response.text)
            self.save()
            response = self.client.post('/api/chat', json=body)
            self.assertEqual(response.status_code, 200)
        self.assertEqual(routes, [('env-chat','https://env.invalid/v1','env-test-key'),
                                  ('saved-chat','https://saved.invalid/v1','saved-test-key')])


if __name__ == '__main__':
    unittest.main()
