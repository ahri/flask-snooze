# coding: utf-8
from unittest import TestCase
from flask import Flask
from flask.ext.testing import TestCase as FlaskTestCase
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.snooze import Snooze, SqlAlchemyEndpoint
from sqlalchemy.orm import object_mapper
from datetime import datetime
import json
import re

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
#           Give a list of supported /book verbs (notify of auth req?)
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

def print_tb(response):
    from traceback import format_list
    try:
        print '\n'.join(format_list(response.json['detail']['traceback']))
    except TypeError:
        pass  # don't care


def data_model(db):
    # Data model
    class Book(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        created = db.Column(db.DateTime(timezone=False), default=datetime.utcnow)
        title = db.Column(db.String(80), unique=True, nullable=False)

        def __iter__(self):
            self._i = iter(object_mapper(self).columns)
            return self

        def next(self):
            n = self._i.next().name
            a = getattr(self, n)
            if type(a) == datetime:
                a = str(a)
            return n, a

    return dict(Book=Book)


class TestSnoozeDirect(TestCase):

    """
    Ensure that the API manager can be used to configure an API.
    """

    def setUp(self):
        self.app = Flask(__name__)
        self.db = SQLAlchemy(self.app)

        self.Book = data_model(self.db)['Book']
        self.db.create_all()

    def tearDown(self):
        """Clean up after each test"""
        self.db.session.remove()
        self.db.drop_all()

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
        obj_name = 'book'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assertIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])

    def test_add_named(self):
        """Pass a model to generate an api from, but ask for a different name"""
        apimgr = self.create_mgr()
        obj_name = 'llyfr'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']), obj_name)
        self.assertIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])

    def test_add_selective(self):
        """Selectively add support for http verbs"""
        apimgr = self.create_mgr()
        obj_name = 'book'
        self.assertNotIn('/%s/' % obj_name, [r.rule for r in self.app.url_map.iter_rules()])
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']), methods=('PUT', 'PATCH'))
        methods = set()
        [methods.update(r.methods) for r in self.app.url_map.iter_rules() if r.rule == '/%s/<obj_id>' % obj_name]
        self.assertEqual(methods, set(['PUT', 'PATCH']))

    def test_no_auto_OPTIONS(self):
        """Flask currently generates OPTIONS rules automatically; this is undesired"""
        apimgr = self.create_mgr()
        obj_name = 'book'
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']), methods=('PUT',))
        methods = set()
        [methods.update(r.methods) for r in self.app.url_map.iter_rules() if r.rule == '/%s/<obj_id>' % obj_name]
        self.assertNotIn('OPTIONS', methods)


class TestSnoozeHttp(FlaskTestCase):

    """
    Ensure that the API manager exposes the correct interface.
    """

    def create_app(self):
        """Create a Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.db = SQLAlchemy(self.app)
        return self.app

    def setUp(self):
        self.Book = data_model(self.db)['Book']
        self.db.create_all()

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
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_not_4xx(self.client.open('/book/', method='OPTIONS'))

    def test_rule_list(self):
        """Test a simple GET against the root of the object API (asking for a "LIST")"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_not_4xx(self.client.get('/book/'))

    def test_rule_post(self):
        """Test a simple POST against the root of the object API"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']), methods=('POST', 'DELETE'))
        self.assert_not_4xx(self.client.post('/book/'))

    def test_rule_get(self):
        """Test a simple GET"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_404(self.client.get('/book/dummy'))

    def test_rule_head(self):
        """Test a simple HEAD"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_404(self.client.head('/book/dummy'))

    def test_rule_put(self):
        """Test a simple PUT"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_not_4xx(self.client.put('/book/dummy'))

    def test_rule_patch(self):
        """Test a simple PATCH"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        r = self.client.patch('/book/dummy')
        self.assert_404(r)

    def test_rule_delete(self):
        """Test a simple DELETE"""
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        self.assert_404(self.client.delete('/book/dummy'))

    #
    # test verbs
    #

    def test_verb_options(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        response = self.client.open('/book/', method='OPTIONS')
        self.assert_200(response)
        options = json.loads(response.data)
        print repr(options)
        self.assertEqual(set(('OPTIONS', 'GET', 'HEAD', 'POST')), set(options['/book/']))
        self.assertEqual(set(('GET', 'HEAD', 'PUT', 'PATCH', 'DELETE')), set(options['/book/<obj_id>']))

    def test_verb_list(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        # add a few books to the db
        b1 = self.Book()
        b2 = self.Book()
        b3 = self.Book()
        b1.title = 'title 1'
        b2.title = 'title 2'
        b3.title = 'title 3'
        self.db.session.add(b1)
        self.db.session.add(b2)
        self.db.session.add(b3)
        self.db.session.flush()

        data = self.client.get('/book/').data
        print data
        lst = json.loads(data)
        self.assertEqual(set([b.id for b in (b1, b2, b3)]), set(lst))

    def test_verb_post(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        title = "test title"
        data_in = dict(title=title)
        response = self.client.post('/book/', data=json.dumps(data_in))
        print_tb(response)
        self.assertStatus(response, 201)
        self.assertIn('Location', response.headers)
        # get the id from the response.headers
        book_id = re.sub('.*/', '', response.headers['Location'])
        book = self.Book.query.filter_by(id=int(book_id)).first()
        self.assertEqual(title, book.title)

    def test_verb_post_location(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        title = "test title"
        data_in = dict(title=title)
        response = self.client.post('/book/', data=json.dumps(data_in))
        self.assertIn('Location', response.headers)
        print "Location:", response.headers['Location']
        self.assertEqual(response.headers['Location'], 'http://localhost/book/1')

    def test_verb_post_500(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))
        data_in = dict(title='title')
        response = self.client.post('/book/', data=json.dumps(data_in))
        response = self.client.post('/book/', data=json.dumps(data_in))
        print response.data
        self.assertEqual(response.status, '500')
        data_out = json.loads(response.data)
        self.assertIn('type', data_out)
        self.assertIn('message', data_out)

    def test_verb_get(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        # add a book to the db
        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()

        response = self.client.get('/book/%s' % book.id)
        data = json.loads(response.data)
        print data
        self.assertEqual(data['title'], book.title)

    def test_verb_get_404(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        # add a book to the db
        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()

        response = self.client.get('/book/%s' % 'dummy')
        print response.data
        self.assert_404(response)
        data = json.loads(response.data)
        print repr(data)
        self.assertIn('detail', data)
        self.assertIn('class', data['detail'])
        self.assertEqual(data['detail']['class'], 'Book')
        self.assertIn('id', data['detail'])
        self.assertEqual(data['detail']['id'], 'dummy')

    def test_verb_head(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()

        response = self.client.head('/book/%s' % book.id)
        self.assert_200(response)
        self.assertEqual(response.data, '')

    def test_verb_head_404(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        response = self.client.head('/book/%s' % 'dummy')
        self.assert_404(response)
        self.assertEqual(response.data, '')

    def test_verb_put_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()
        book_id = book.id

        new_title = 'new title'
        data_in = json.dumps(dict(title=new_title))
        response = self.client.put('/book/%s' % book.id, data=data_in)
        self.assert_200(response)
        # TODO: would be nice to just self.db.session.refresh(book) -- why doesn't this work?
        book = self.Book.query.filter_by(id=book_id).first()
        self.assertEqual(book.title, new_title)

    def test_verb_put_not_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        put_id = 999
        new_title = 'new title'
        data_in = json.dumps(dict(title=new_title))
        response = self.client.put('/book/%s' % put_id, data=data_in)
        self.assertStatus(response, 201)
        new_book_id = int(re.sub('.*/', '', response.headers['Location']))
        book = self.Book.query.filter_by(id=put_id).first()
        self.assertEqual(put_id, new_book_id)
        self.assertEqual(book.title, new_title)

    def test_verb_patch_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()
        book_id = book.id

        new_title = 'new title'
        data_in = json.dumps(dict(title=new_title))
        response = self.client.patch('/book/%s' % book.id, data=data_in)
        self.assert_200(response)
        book = self.Book.query.filter_by(id=book_id).first()
        self.assertEqual(book.title, new_title)

    def test_verb_patch_not_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        put_id = 999
        new_title = 'new title'
        data_in = json.dumps(dict(title=new_title))
        response = self.client.patch('/book/%s' % put_id, data=data_in)
        self.assert_404(response)

    def test_verb_delete_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        book = self.Book()
        book.title = 'title'
        self.db.session.add(book)
        self.db.session.flush()
        book_id = book.id

        response = self.client.delete('/book/%s' % book.id)
        self.assert_200(response)
        book = self.Book.query.filter_by(id=book_id).first()
        self.assertIs(book, None)

    def test_verb_delete_not_existing(self):
        apimgr = self.create_mgr()
        apimgr.add(SqlAlchemyEndpoint(self.db, self.Book, ['title']))

        put_id = 999
        response = self.client.delete('/book/%s' % put_id)
        self.assert_404(response)
