"""
Copyright (c) 2011 The Native Client Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

import cgi
import datetime
import json
import logging
import os
import urllib
import wsgiref.handlers

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.db import Key
from google.appengine.ext.webapp import Request
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app


"""
This script is an example server backend for use with the App Engine
mount type in nacl-mounts.
"""


class File(db.Model):
  owner = db.UserProperty()
  filename = db.StringProperty()
  data = db.BlobProperty()


class MainPage(webapp.RequestHandler):
  def get(self):
    # Require the user to login.
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.uri))
      return

    self.response.headers['Access-Control-Allow-Origin'] = (
        'chrome-extension://ladkaalcnedlcimjgaldjoeahnklilnk/')
    self.response.headers['Access-Control-Allow-Credentials'] = 'true'
    self.response.out.write('<html>\n')
    self.response.out.write('<head>\n')
    self.response.out.write('<title>NaClHack</title>\n')
    self.response.out.write('</head>\n')
    self.response.out.write('<body>\n')
    self.response.out.write('[ %s ] <a href="%s">Sign out</a>' % (
        user.email(),
        users.create_logout_url(self.request.uri)))
    self.response.out.write('</body>\n')
    self.response.out.write('</html>\n')


class ClosePage(webapp.RequestHandler):
  def get(self):
    self.response.out.write('\n'.join([
      '<html>',
      '<head>',
      '<title>NaClHack</title>',
      '</head>',
      '<body onload="window.close();">',
      '</body>',
      '</html>',
    ]) + '\n')


class StatusPage(webapp.RequestHandler):
  def get(self):
    self.response.headers['Access-Control-Allow-Origin'] = (
        'chrome-extension://ladkaalcnedlcimjgaldjoeahnklilnk/')
    self.response.headers['Access-Control-Allow-Credentials'] = 'true'
    self.response.headers['Content-Type'] = 'application/json'
    reply = {}
    user = users.get_current_user()
    if user:
      reply['logged_in'] = True
      reply['email'] = user.email()
      reply['nickname'] = user.nickname()
      reply['logout_url'] = users.create_logout_url('/_close')
    else:
      reply['logged_in'] = False
      reply['login_url'] = users.create_login_url('/_close')
    self.response.out.write(json.dumps(reply))


def FileKey(filename, user):
  if not user:
    u_id = -1
  else:
    u_id = user.user_id()
  return Key.from_path('File', '%s_%s' % (filename, u_id))


class FileHandlingPage(webapp.RequestHandler):
  def post(self):
    user = users.get_current_user()

    split = self.request.path.rsplit('/', 1)
    assert (len(split) > 1)
    method = split[1]

    self.response.headers['Content-Type'] = 'application/octet-stream'
    self.response.headers['Access-Control-Allow-Origin'] = (
        'chrome-extension://ladkaalcnedlcimjgaldjoeahnklilnk/')
    self.response.headers['Access-Control-Allow-Credentials'] = 'true'
    
    if method == 'read':
      filename = self.request.get(u'filename')
      assert filename
      logging.info('reading %s' % filename)
      k = FileKey(filename, user)
      f = File.get(k)
      if f:
        self.response.out.write(f.data)
        self.response.out.write('1')
      else:
        self.response.out.write('0')

    elif method == 'write':
      self.response.out.write('1')
      data = self.request.get(u'data')
      filename = self.request.get(u'filename')
      assert filename
      assert data
      logging.info('writing %s size=%d' % (filename, len(data)))
      def create_or_update(filename, data, owner):
        k = FileKey(filename, user)
        f = File.get(k)
        if not f:
          f = File(key=k)
          f.owner = owner
          f.filename = filename
        f.data = data
        return f

      f = db.run_in_transaction(create_or_update, filename, data, user)

      def db_put(file):
        f.put()

      db.run_in_transaction(db_put, f)

    elif method == 'list':
      prefix = self.request.get(u'prefix')
      assert prefix
      # First make sure that the file is there
      k = FileKey(prefix, user)
      f = File.get(k)
      if not f:
        return
      q = File.all()
      q.filter('owner =', user)
      q.filter('filename >', prefix)
      q.filter('filename <', prefix + u'ffff')
      prefixslash = prefix
      if prefixslash[-1] != '/':
        prefixslash += '/'
      depth = len(prefixslash.split('/'))
      results = q.fetch(limit=100)
      for r in results:
        # make sure the file is directly under prefixslash
        if len(r.filename.split('/')) != depth:
          continue
        self.response.out.write('%s\n' % r.filename)

    elif method == 'remove':
      filename = self.request.get(u'filename')
      assert filename
      k = FileKey(filename, user)
      try:
        db.delete(k)
        self.response.out.write('1')
      except:
        self.response.out.write('0')
        return

    else:
      assert False


application = webapp.WSGIApplication([
  ('/', MainPage),
  ('/_status', StatusPage),
  ('/_close', ClosePage),
  ('/_file/.*', FileHandlingPage),

], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
