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

# TODO: selective auth per "add"
# TODO: basic auth function generator
#
# TODO: try to set properties (in ._update()) with a method, e.g.
#       rest_set(p, v, auth=False) so that the user can control access
#       the auth param can be an item passed back from the auth function
#       hook, for similar reasons


# TODO: don't throw back tracebacks unless debug is switched on (i.e. add a
#       debug switch)

# TODO: see auth status of verbs in OPTIONS

# TODO: Support:
#           If-Modified-Since, If-Unmodified-Since, If-Match,
#           If-None-Match, If-Range

# TODO: Ensure that Content-Length, Content-MD5, ETag and Last-Modified
#           are sent.

# GET/OPTIONS support needs neatening up
# /api_v1
#   GET: lists objects
#   OPTIONS: lists objects and supported verbs for them, including auth_reqd
# /api_v1/obj_name
#   GET: give all objects (pagination??)
#   OPTIONS: lists supported verbs, including auth_reqd


class DummyEndpoint(Endpoint):
    pass


def print_tb(response):
    from traceback import format_list
    try:
        print '\n'.join(format_list(response.json['detail']['traceback']))
    except TypeError:
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
