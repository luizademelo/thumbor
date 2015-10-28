#!/usr/bin/python
# -*- coding: utf-8 -*-

# thumbor imaging service
# https://github.com/thumbor/thumbor/wiki

# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2011 globo.com timehome@corp.globo.com

from urllib import quote
import tempfile
import shutil
from os.path import abspath, join, dirname

import tornado.web
from preggy import expect
from mock import Mock

from thumbor.config import Config
from thumbor.importer import Importer
from thumbor.context import Context, ServerParameters
from thumbor.handlers import FetchResult, BaseHandler
from thumbor.utils import which
from tests.base import TestCase, PythonTestCase
from tests.fixtures.images import (
    default_image,
    alabama1,
    space_image,
    invalid_quantization,
)


class FetchResultTestCase(PythonTestCase):
    def test_can_create_default_fetch_result(self):
        result = FetchResult()
        expect(result.normalized).to_be_false()
        expect(result.buffer).to_be_null()
        expect(result.engine).to_be_null()
        expect(result.successful).to_be_false()
        expect(result.loader_error).to_be_null()

    def test_can_create_fetch_result(self):
        buffer_mock = Mock()
        engine_mock = Mock()
        error_mock = Mock()
        result = FetchResult(
            normalized=True,
            buffer=buffer_mock,
            engine=engine_mock,
            successful=True,
            loader_error=error_mock,
        )
        expect(result.normalized).to_be_true()
        expect(result.buffer).to_equal(buffer_mock)
        expect(result.engine).to_equal(engine_mock)
        expect(result.successful).to_be_true()
        expect(result.loader_error).to_equal(error_mock)


class ErrorHandler(BaseHandler):
    def get(self):
        self._error(403)


class BaseHandlerTestApp(tornado.web.Application):
    def __init__(self, context):
        self.context = context
        super(BaseHandlerTestApp, self).__init__([
            (r'/error', ErrorHandler),
        ])


class BaseHandlerTestCase(TestCase):
    def get_app(self):
        self.context = self.get_context()
        return BaseHandlerTestApp(self.context)

    def test_can_get_an_error(self):
        response = self.fetch('/error')
        expect(response.code).to_equal(403)


class BaseImagingTestCase(TestCase):
    @classmethod
    def setUpClass(cls, *args, **kw):
        cls.root_path = tempfile.mkdtemp()
        cls.loader_path = abspath(join(dirname(__file__), '../fixtures/images/'))
        cls.base_uri = "/image"

    @classmethod
    def tearDownClass(cls, *args, **kw):
        shutil.rmtree(cls.root_path)


class ImagingOperationsTestCase(BaseImagingTestCase):
    def get_context(self):
        cfg = Config(SECURITY_KEY='ACME-SEC')
        cfg.LOADER = "thumbor.loaders.file_loader"
        cfg.FILE_LOADER_ROOT_PATH = self.loader_path
        cfg.STORAGE = "thumbor.storages.file_storage"
        cfg.FILE_STORAGE_ROOT_PATH = self.root_path

        importer = Importer(cfg)
        importer.import_modules()
        server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        server.security_key = 'ACME-SEC'
        return Context(server, cfg, importer)

    def test_can_get_image(self):
        response = self.fetch('/unsafe/smart/image.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(default_image())

    def test_can_get_image_without_extension(self):
        response = self.fetch('/unsafe/smart/image')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(default_image())

    def test_get_unknown_image_returns_not_found(self):
        response = self.fetch('/unsafe/smart/imag')
        expect(response.code).to_equal(404)

    def test_can_get_unicode_image(self):
        response = self.fetch(u'/unsafe/%s' % quote(u'15967251_212831_19242645_АгатавЗоопарке.jpg'.encode('utf-8')))
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(default_image())

    def test_can_get_signed_regular_image(self):
        response = self.fetch('/_wIUeSaeHw8dricKG2MGhqu5thk=/smart/image.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(default_image())

    def test_url_without_unsafe_or_hash_fails(self):
        response = self.fetch('/alabama1_ap620%C3%A9.jpg')
        expect(response.code).to_equal(400)

    def test_url_without_image(self):
        response = self.fetch('/unsafe/')
        expect(response.code).to_equal(400)

    def test_utf8_encoded_image_name_with_encoded_url(self):
        url = '/lc6e3kkm_2Ww7NWho8HPOe-sqLU=/smart/alabama1_ap620%C3%A9.jpg'
        response = self.fetch(url)
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(alabama1())

    def test_image_with_spaces_on_url(self):
        response = self.fetch(u'/unsafe/image%20space.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(space_image())

    def test_can_get_image_with_filter(self):
        response = self.fetch('/5YRxzS2yxZxj9SZ50SoZ11eIdDI=/filters:fill(blue)/image.jpg')
        expect(response.code).to_equal(200)

    def test_can_get_image_with_invalid_quantization_table(self):
        response = self.fetch('/unsafe/invalid_quantization.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(invalid_quantization())

    def test_getting_invalid_image_returns_bad_request(self):
        response = self.fetch('/unsafe/image_invalid.jpg')
        expect(response.code).to_equal(400)

    def test_can_read_monochromatic_jpeg(self):
        response = self.fetch('/unsafe/wellsford.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_jpeg()

    def test_can_read_image_with_small_width_and_no_height(self):
        response = self.fetch('/unsafe/0x0:1681x596/1x/hidrocarbonetos_9.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_jpeg()


class ImageOperationsWithoutUnsafeTestCase(BaseImagingTestCase):
    def get_context(self):
        cfg = Config(SECURITY_KEY='ACME-SEC')
        cfg.LOADER = "thumbor.loaders.file_loader"
        cfg.FILE_LOADER_ROOT_PATH = self.loader_path
        cfg.ALLOW_UNSAFE_URL = False

        importer = Importer(cfg)
        importer.import_modules()
        server = ServerParameters(8890, 'localhost', 'thumbor.conf', None, 'info', None)
        server.security_key = 'ACME-SEC'
        return Context(server, cfg, importer)

    def test_can_get_image_with_signed_url(self):
        response = self.fetch('/_wIUeSaeHw8dricKG2MGhqu5thk=/smart/image.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_similar_to(default_image())

    def test_getting_unsafe_image_fails(self):
        response = self.fetch('/unsafe/smart/image.jpg')
        expect(response.code).to_equal(400)


class ImageOperationsWithStoredKeysTestCase(BaseImagingTestCase):
    def get_context(self):
        cfg = Config(SECURITY_KEY='MYKEY')
        cfg.LOADER = "thumbor.loaders.file_loader"
        cfg.FILE_LOADER_ROOT_PATH = self.loader_path
        cfg.ALLOW_UNSAFE_URL = False
        cfg.ALLOW_OLD_URLS = True
        cfg.STORES_CRYPTO_KEY_FOR_EACH_IMAGE = True

        importer = Importer(cfg)
        importer.import_modules()
        server = ServerParameters(8891, 'localhost', 'thumbor.conf', None, 'info', None)
        server.security_key = 'MYKEY'
        return Context(server, cfg, importer)

    def test_stored_security_key_with_regular_image(self):
        storage = self.context.modules.storage
        self.context.server.security_key = 'MYKEY'
        storage.put_crypto('image.jpg')   # Write a file on the file storage containing the security key
        self.context.server.security_key = 'MYKEY2'

        try:
            response = self.fetch('/nty7gpBIRJ3GWtYDLLw6q1PgqTo=/smart/image.jpg')
            expect(response.code).to_equal(200)
            expect(response.body).to_be_similar_to(default_image())
        finally:
            self.context.server.security_key = 'MYKEY'

    def test_stored_security_key_with_regular_image_with_querystring(self):
        storage = self.context.modules.storage
        self.context.server.security_key = 'MYKEY'
        storage.put_crypto('image.jpg')   # Write a file on the file storage containing the security key
        self.context.server.security_key = 'MYKEY2'

        try:
            response = self.fetch('/Iw7LZGdr-hHj2gQ4ZzksP3llQHY=/smart/image.jpg%3Fts%3D1')
            expect(response.code).to_equal(200)
            expect(response.body).to_be_similar_to(default_image())
        finally:
            self.context.server.security_key = 'MYKEY'

    def test_stored_security_key_with_regular_image_with_hash(self):
        storage = self.context.modules.storage
        self.context.server.security_key = 'MYKEY'
        storage.put_crypto('image.jpg')   # Write a file on the file storage containing the security key
        self.context.server.security_key = 'MYKEY2'

        try:
            response = self.fetch('/fxOHtHcTZMyuAQ1YPKh9KWg7nO8=/smart/image.jpg%23something')
            expect(response.code).to_equal(200)
            expect(response.body).to_be_similar_to(default_image())
        finally:
            self.context.server.security_key = 'MYKEY'


class ImageOperationsWithAutoWebPTestCase(BaseImagingTestCase):
    _multiprocess_can_split_ = True

    def get_context(self):
        cfg = Config(SECURITY_KEY='ACME-SEC')
        cfg.LOADER = "thumbor.loaders.file_loader"
        cfg.FILE_LOADER_ROOT_PATH = self.loader_path
        cfg.STORAGE = "thumbor.storages.no_storage"
        cfg.AUTO_WEBP = True

        importer = Importer(cfg)
        importer.import_modules()
        server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        server.security_key = 'ACME-SEC'
        ctx = Context(server, cfg, importer)
        ctx.server.gifsicle_path = which('gifsicle')
        return ctx

    def get_as_webp(self, url):
        return self.fetch(url, headers={
            "Accept": 'image/webp,*/*;q=0.8'
        })

    def test_can_auto_convert_jpeg(self):
        response = self.get_as_webp('/unsafe/image.jpg')
        expect(response.code).to_equal(200)
        expect(response.headers).to_include('Vary')
        expect(response.headers['Vary']).to_include('Accept')

        expect(response.body).to_be_webp()

    def test_should_not_convert_webp_if_already_webp(self):
        response = self.get_as_webp('/unsafe/image.webp')

        expect(response.code).to_equal(200)
        expect(response.headers).not_to_include('Vary')
        expect(response.body).to_be_webp()

    def test_should_not_convert_webp_if_bigger_than_89478485_pixels(self):
        response = self.get_as_webp('/unsafe/16384.png')

        expect(response.code).to_equal(200)
        expect(response.headers).not_to_include('Vary')
        expect(response.body).to_be_png()

    def test_should_not_convert_animated_gifs_to_webp(self):
        response = self.get_as_webp('/unsafe/animated_image.gif')

        expect(response.code).to_equal(200)
        expect(response.headers).not_to_include('Vary')
        expect(response.body).to_be_gif()

    def test_should_convert_image_with_small_width_and_no_height(self):
        response = self.get_as_webp('/unsafe/0x0:1681x596/1x/hidrocarbonetos_9.jpg')

        expect(response.code).to_equal(200)
        expect(response.body).to_be_webp()

    def test_can_read_monochromatic_jpeg(self):
        response = self.get_as_webp('/unsafe/wellsford.jpg')
        expect(response.code).to_equal(200)
        expect(response.body).to_be_webp()

    #class WithCMYKJPEG(BaseContext):
        #def topic(self):
            #response = self.fetch('/unsafe/merrit.jpg')
            #return (response.code, response.headers)

        #def should_be_200(self, response):
            #code, _ = response
            #expect(code).to_equal(200)

    #class WithCMYKJPEGAsPNG(BaseContext):
        #def topic(self):
            #response = self.fetch('/unsafe/filters:format(png)/merrit.jpg')
            #return (response.code, response.headers)

        #def should_be_200(self, response):
            #code, _ = response
            #expect(code).to_equal(200)

    #class WithCMYKJPEGAsPNGAcceptingWEBP(BaseContext):
        #def topic(self):
            #response = self.fetch('/unsafe/filters:format(png)/merrit.jpg', headers={
                #"Accept": 'image/webp,*/*;q=0.8'
            #})
            #return response

        #def should_be_200(self, response):
            #expect(response.code).to_equal(200)
            #image = self.engine.create_image(response.body)
            #expect(image.format.lower()).to_equal('png')

    #class WithJPEGAsGIFAcceptingWEBP(BaseContext):
        #def topic(self):
            #response = self.fetch('/unsafe/filters:format(gif)/image.jpg', headers={
                #"Accept": 'image/webp,*/*;q=0.8'
            #})
            #return response

        #def should_be_200(self, response):
            #expect(response.code).to_equal(200)
            #image = self.engine.create_image(response.body)
            #expect(image.format.lower()).to_equal('gif')

    #class HasEtags(BaseContext):
        #def topic(self):
            #return self.fetch('/unsafe/image.jpg', headers={
                #"Accept": 'image/webp,*/*;q=0.8'
            #})

        #def should_have_etag(self, response):
            #expect(response.headers).to_include('Etag')


#@Vows.batch
#class GetImageWithoutEtags(BaseContext):
    #def get_app(self):
        #cfg = Config(SECURITY_KEY='ACME-SEC')
        #cfg.LOADER = "thumbor.loaders.file_loader"
        #cfg.FILE_LOADER_ROOT_PATH = storage_path
        #cfg.ENABLE_ETAGS = False

        #importer = Importer(cfg)
        #importer.import_modules()
        #server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        #server.security_key = 'ACME-SEC'
        #ctx = Context(server, cfg, importer)
        #application = ThumborServiceApp(ctx)

        #self.engine = PILEngine(ctx)

        #return application

    #class CanDisableEtag(BaseContext):
        #def topic(self):
            #return self.fetch('/unsafe/image.jpg', headers={
                #"Accept": 'image/webp,*/*;q=0.8'
            #})

        #def should_not_have_etag(self, response):
            #expect(response.headers).not_to_include('Etag')


#@Vows.batch
#class GetImageWithGIFV(BaseContext):
    #def get_app(self):
        #cfg = Config(SECURITY_KEY='ACME-SEC')
        #cfg.LOADER = "thumbor.loaders.file_loader"
        #cfg.FILE_LOADER_ROOT_PATH = storage_path
        #cfg.OPTIMIZERS = [
            #'thumbor.optimizers.gifv',
        #]

        #importer = Importer(cfg)
        #importer.import_modules()
        #server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        #server.security_key = 'ACME-SEC'
        #ctx = Context(server, cfg, importer)
        #ctx.server.gifsicle_path = which('gifsicle')
        #application = ThumborServiceApp(ctx)

        #self.engine = PILEngine(ctx)

        #return application

    #class ShouldConvertAnimatedGifToMp4WhenFilter(BaseContext):
        #def topic(self):
            #return self.fetch('/unsafe/filters:gifv()/animated_image.gif')

        #def should_be_mp4(self, response):
            #expect(response.code).to_equal(200)
            #expect(response.headers['Content-Type']).to_equal('video/mp4')

    #class ShouldConvertAnimatedGifToWebmWhenFilter(BaseContext):
        #def topic(self):
            #return self.fetch('/unsafe/filters:gifv(webm)/animated_image.gif')

        #def should_be_mp4(self, response):
            #expect(response.code).to_equal(200)
            #expect(response.headers['Content-Type']).to_equal('video/webm')


#@Vows.batch
#class GetImageCover(BaseContext):
    #def get_app(self):
        #cfg = Config(SECURITY_KEY='ACME-SEC')
        #cfg.LOADER = "thumbor.loaders.file_loader"
        #cfg.FILE_LOADER_ROOT_PATH = storage_path
        #cfg.AUTO_WEBP = True
        #cfg.USE_GIFSICLE_ENGINE = True

        #importer = Importer(cfg)
        #importer.import_modules()
        #server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        #server.security_key = 'ACME-SEC'
        #ctx = Context(server, cfg, importer)
        #ctx.server.gifsicle_path = which('gifsicle')
        #application = ThumborServiceApp(ctx)

        #self.engine = PILEngine(ctx)

        #return application

    #class ShouldExtractCover(BaseContext):
        #def topic(self):
            #return self.fetch('/unsafe/filters:cover()/animated_image.gif')

        #def should_be_webp(self, response):
            #expect(response.code).to_equal(200)
            #expect(response.headers['Content-Type']).to_equal('image/gif')


#@Vows.batch
#class GetImageResultStorage(BaseContext):
    #def get_app(self):
        #cfg = Config(SECURITY_KEY='ACME-SEC')
        #cfg.LOADER = "thumbor.loaders.file_loader"
        #cfg.FILE_LOADER_ROOT_PATH = storage_path
        #cfg.RESULT_STORAGE = 'thumbor.result_storages.file_storage'
        #cfg.RESULT_STORAGE_EXPIRATION_SECONDS = 60
        #cfg.RESULT_STORAGE_FILE_STORAGE_ROOT_PATH = tempfile.mkdtemp(prefix='thumbor_test')
        #cfg.USE_GIFSICLE_ENGINE = True
        #cfg.AUTO_WEBP = True
        #cfg.OPTIMIZERS = [
            #'thumbor.optimizers.gifv',
        #]

        #importer = Importer(cfg)
        #importer.import_modules()
        #server = ServerParameters(8889, 'localhost', 'thumbor.conf', None, 'info', None)
        #server.security_key = 'ACME-SEC'
        #ctx = Context(server, cfg, importer)
        #ctx.server.gifsicle_path = which('gifsicle')
        #application = ThumborServiceApp(ctx)

        #self.engine = PILEngine(ctx)

        #return application

    #class ShouldLoadGifFromResultStorage(BaseContext):
        #def topic(self):
            #self.fetch('/P_leK0uires4J3AXg5RkKfSWH4A=/animated_image.gif')  # Add to result Storage
            #return self.fetch('/P_leK0uires4J3AXg5RkKfSWH4A=/animated_image.gif')

        #def should_ok(self, response):
            #expect(response.code).to_equal(200)

    #class ShouldLoadGifVFromResultStorage(BaseContext):
        #def topic(self):
            #self.fetch('/degWAAUDokT-7K81r2BXoPTbg8c=/filters:gifv()/animated_image.gif')  # Add to result Storage
            #return self.fetch('/degWAAUDokT-7K81r2BXoPTbg8c=/filters:gifv()/animated_image.gif')

        #def should_ok(self, response):
            #expect(response.code).to_equal(200)
