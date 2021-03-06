# coding: utf-8
from unittest import TestCase
from flask import Flask
from flask.ext.testing import TestCase as FlaskTestCase
from flask.ext.snooze import Snooze, Endpoint

try:
    import simplejson as json
except ImportError:
    import json

"""
Api Manager Tests
HTTP Protocol reference: http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html
"""

#
#       GENERAL:
#           Content-Type should be passed, possibly required by data_out
#           hook?
#           What is a 204?
#               "Request processed successfully, but no content is being
#               returned" -- which should be useful
#       OPTIONS:
#           Give a list of supported /object verbs (notify of auth req?)
#       GET:
#           Would be good to support req headers:
#               If-Modified-Since, If-Unmodified-Since, If-Match,
#               If-None-Match, If-Range
#           Ensure that Content-Length, Content-MD5, ETag and Last-Modified
#           are sent.
#       HEAD:
#           Identical to GET (including headers to send back), must not
#           return body.
#       POST:
#           If it doesn't create anything it should return 200 or 204.
#           If it does create something it should return 201 and a Location
#       PUT:
#           If it's replacing an existing object return a 200 or 204
#           Otherwise add a new object and then return a 201
#       PATCH:
#           Same as above (at a guess) but cannot create objects
#       DELETE:
#           return 200 if it's deleting right away
#           return 202 if it will be deleted later
#           or return 204
#       TRACE:
#           Probably best to ignore this for now.


class DummyEndpoint(Endpoint):

    """
    Base Endpoint object.
    """

    def __init__(self, cls, id_key, writeable_keys):
        """
        cls:            Class of object being represented by this endpoint
        id_key:         Identifying key of an object
        writeable_keys: A list of keys that may be written to on an object
        """
        super(DummyEndpoint, self).__init__(cls, id_key, writeable_keys)

        self.calls = []

    def create(self, path=None):
        """Create a new object"""
        self.calls.append(('create', dict(path=path)))

    def read(self, path):
        """Load an existing object"""
        self.calls.append(('read', dict(path=path)))
        if path is None:
            return []

    def finalize(self, obj):
        """Save an object (if required)"""
        self.calls.append(('finalize', dict(obj=obj)))

    def delete(self, path):
        """Delete the data for the provided ID"""
        self.calls.append(('delete', dict(path=path)))


def print_tb(response):
    from traceback import format_list
    try:
        response = response.json
        print response['message']
        print
        print '\n'.join(format_list(response['detail']['traceback']))
    except (TypeError, KeyError):
        pass  # don't care


class TestSnoozeDirect(TestCase):

    """
    Ensure that the API manager can be used to configure an API.
    """

    def setUp(self):
        self.app = Flask(__name__)

    def create_mgr(self):
        """Helper to create a context"""
        return Snooze(self.app)

    def test_init(self):
        """Create a Snooze API manager context"""
        c = self.create_mgr()
        self.assertIsInstance(c, Snooze)

    def test_add(self):
        """Pass a model to generate an api from"""
        apimgr = self.create_mgr()
        obj_name = 'object'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(DummyEndpoint(object, None, None))
        self.assertIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])

    def test_add_named(self):
        """Pass a model to generate an api from, but ask for a different name"""
        apimgr = self.create_mgr()
        obj_name = 'llyfr'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(DummyEndpoint(object, None, None), obj_name)
        self.assertIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])

    def test_add_selective(self):
        """Selectively add support for http verbs"""
        apimgr = self.create_mgr()
        obj_name = 'object'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(DummyEndpoint(object, None, None), methods=('PUT', 'PATCH'))
        methods = set()
        [methods.update(r.methods) for r in self.app.url_map.iter_rules() if r.rule == '/%s/<path:path>' % obj_name]
        self.assertEqual(methods, set(['PUT', 'PATCH']))

    def test_no_auto_OPTIONS(self):
        """Flask currently generates OPTIONS rules automatically; this is undesired"""
        apimgr = self.create_mgr()
        obj_name = 'object'
        apimgr.add(DummyEndpoint(object, None, None), methods=('PUT',))
        methods = set()
        [methods.update(r.methods) for r in self.app.url_map.iter_rules() if r.rule == '/%s/<path:path>' % obj_name]
        self.assertNotIn('OPTIONS', methods)


class TestSnoozeHttp(FlaskTestCase):

    """
    Ensure that the API manager exposes the correct interface.
    """

    def create_app(self):
        """Create a Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        return self.app

    def create_mgr(self):
        """Helper to create a context"""
        return Snooze(self.app)

    def assert_not_4xx(self, response):
        code = response.status_code
        self.assertFalse(str(code).startswith('4'),
            "%d received, expecting a non-4xx code" % code)

    # test rules
    def test_rule_options(self):
        """Test a simple OPTIONS against the root of the object API"""
        apimgr = self.create_mgr()
        apimgr.add(DummyEndpoint(object, None, None))
        self.assert_not_4xx(self.client.open('/object/', method='OPTIONS'))

    def test_verb_options(self):
        apimgr = self.create_mgr()
        apimgr.add(DummyEndpoint(object, None, None))
        response = self.client.open('/object/', method='OPTIONS')
        self.assert_200(response)
        options = json.loads(response.data)
        print repr(options)
        self.assertEqual(set(('OPTIONS', 'GET', 'HEAD', 'POST')), set(options['/object/']))
        print [(r.rule, r.methods, r.endpoint) for r in self.app.url_map.iter_rules()]
        self.assertEqual(set(('OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE')), set(options['/object/<path:path>']))

    # check that lists behave properly
    def test_list(self):
        apimgr = self.create_mgr()
        apimgr.add(DummyEndpoint(object, None, None))
        response = self.client.get('/object/')
        self.assertIsInstance(response.json, list)


class TestExerciseEndpoint(FlaskTestCase):

    """
    Exercise the verbs using a dummy endpoint to record calls.
    """

    def create_app(self):
        """Create a Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        return self.app

    def setUp(self):
        self.endpoint = DummyEndpoint(object, None, None)
        self.mgr = Snooze(self.app)
        self.mgr.add(self.endpoint)
        print [(r.rule, r.methods, r.endpoint) for r in self.app.url_map.iter_rules()]

    def test_post_no_path(self):
        path = ''
        self.client.post('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('create', dict(path=None))])

    def test_post_path(self):
        path = 'foo'
        self.client.post('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('create', dict(path=path))])

    def test_get_no_path(self):
        path = ''
        self.client.get('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('read', dict(path=None))])

    def test_get_path(self):
        path = 'foo'
        self.client.get('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('read', dict(path=path))])

    def test_put_no_path(self):
        path = ''
        self.assert_status(self.client.put('/object/%s' % path), 405)

    def test_put_path(self):
        path = 'foo'
        self.client.put('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('read', dict(path=path))])

    def test_patch_no_path(self):
        path = ''
        self.assert_status(self.client.patch('/object/%s' % path), 405)

    def test_patch_path(self):
        path = 'foo'
        self.client.patch('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('read', dict(path=path)),
                                               ('finalize', dict(obj=None))])

    def test_delete_no_path(self):
        path = ''
        self.assert_status(self.client.delete('/object/%s' % path), 405)

    def test_delete_path(self):
        path = 'foo'
        self.client.delete('/object/%s' % path)
        self.assertEqual(self.endpoint.calls, [('delete', dict(path=path))])
