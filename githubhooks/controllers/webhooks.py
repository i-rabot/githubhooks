# -*- coding: utf-8 -*-
"""WebHooks controller module"""
from githubhooks.lib.base import BaseController
from tg import expose, request, config
import json
import github
import hashlib
import hmac
# from tg.i18n import ugettext as _
# from tg import predicates

import logging
log = logging.getLogger(__name__)


class _InspectionManager(object):
    
    def __init__(self, repo_dict):
        self.hub = github.Github(
            config['githublogin'],
            config['githubpasswd'])
        self.owner = self.hub.get_user(repo_dict['owner']['name'])
        self.repo = self.owner.get_repo(repo_dict['name'])
        if not self.repo:
            raise AssertionError("Couldn't load repo")
    
    def get_commit(self, commitid):
        return self.repo.get_commit(commitid)
    

class WebHooksController(BaseController):

    # Uncomment this line if your controller requires an authenticated user
    # allow_only = predicates.not_anonymous()
    
    def validate_signature(self):
        dig = hmac.new(config['webhook_secret'], request.body, hashlib.sha1)
        calculated_sig = "sha1=" + dig.hexdigest()
        if calculated_sig != request.environ['HTTP_X_HUB_SIGNATURE']:
            # not from github or secret is set incorrectly
            raise AssertionError("signature mismatch!")
    
    @expose()
    def inspect_push(self, payload):
        self.validate_signature()
        log.debug("%r" % payload)
        payload = json.loads(payload, encoding=request.charset)
        log.info("Processing this push: %s" % payload['compare'])
        manager = _InspectionManager(payload['repository'])
        for c in payload['commits']:
            commit = manager.get_commit(c['id'])
            commit.create_status('pending', description='checking commit...')
        return "Finished"
        